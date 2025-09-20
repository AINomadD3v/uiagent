/**
 * Sophisticated Python Traceback Extraction Utility
 *
 * This module provides advanced traceback parsing and extraction capabilities
 * that match the legacy implementation's regex patterns and logic.
 */

export interface TracebackInfo {
	/** The full extracted traceback string */
	traceback: string;
	/** The error type (e.g., "ValueError", "TypeError") */
	errorType?: string;
	/** The error message */
	errorMessage?: string;
	/** Individual stack frames */
	stackFrames: StackFrame[];
	/** Whether this appears to be a complete traceback */
	isComplete: boolean;
}

export interface StackFrame {
	/** File path where the error occurred */
	file: string;
	/** Line number in the file */
	line: number;
	/** Function or method name */
	function?: string;
	/** The actual code line that caused the error */
	code?: string;
}

/**
 * Traceback keywords that indicate the start of an error traceback
 */
const TRACEBACK_KEYWORDS = [
	'Traceback (most recent call last):',
	'Traceback (most recent call last)',
	'Exception in thread',
	'ERROR:',
	'CRITICAL:'
];

/**
 * Regex patterns for parsing different parts of a traceback
 */
const TRACEBACK_PATTERNS = {
	// Matches stack frame lines like: '  File "/path/file.py", line 123, in function_name'
	stackFrame: /^\s*File\s+"([^"]+)",\s*line\s+(\d+)(?:,\s*in\s+(.+))?$/,

	// Matches code lines that follow stack frames (usually indented)
	codeLine: /^\s{4,}(.+)$/,

	// Matches error type and message like: 'ValueError: invalid literal for int()'
	errorTypeMessage: /^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*:\s*(.*)$/,

	// Matches standalone error types without messages
	errorTypeOnly: /^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$/
};

/**
 * Extract and parse the most recent traceback from console output
 */
export function extractTraceback(outputText: string): TracebackInfo | null {
	if (!outputText || typeof outputText !== 'string') {
		return null;
	}

	// Find the most recent traceback keyword
	let lastErrorIndex = -1;
	let foundKeyword: string | null = null;

	for (const keyword of TRACEBACK_KEYWORDS) {
		const currentIndex = outputText.lastIndexOf(keyword);
		if (currentIndex > lastErrorIndex) {
			lastErrorIndex = currentIndex;
			foundKeyword = keyword;
		}
	}

	if (lastErrorIndex === -1 || !foundKeyword) {
		return null;
	}

	// Extract potential traceback from the keyword to the end
	const potentialTraceback = outputText.substring(lastErrorIndex);
	const lines = potentialTraceback.split(/\r?\n/);

	// Parse the traceback to find its actual end
	const tracebackInfo = parseTraceback(lines, foundKeyword);

	if (!tracebackInfo) {
		return null;
	}

	return tracebackInfo;
}

/**
 * Parse traceback lines and extract structured information
 */
function parseTraceback(lines: string[], keyword: string): TracebackInfo | null {
	if (!lines || lines.length === 0) {
		return null;
	}

	const stackFrames: StackFrame[] = [];
	let errorType: string | undefined;
	let errorMessage: string | undefined;
	let tracebackEndIndex = lines.length - 1;
	let isComplete = false;

	// Start parsing from line 1 (skip the "Traceback..." line)
	let i = 1;

	while (i < lines.length) {
		const line = lines[i];

		// Skip empty lines
		if (!line.trim()) {
			i++;
			continue;
		}

		// Try to match stack frame
		const frameMatch = line.match(TRACEBACK_PATTERNS.stackFrame);
		if (frameMatch) {
			const frame: StackFrame = {
				file: frameMatch[1],
				line: parseInt(frameMatch[2], 10),
				function: frameMatch[3]
			};

			// Check if the next line contains the code
			if (i + 1 < lines.length) {
				const nextLine = lines[i + 1];
				const codeMatch = nextLine.match(TRACEBACK_PATTERNS.codeLine);
				if (codeMatch) {
					frame.code = codeMatch[1].trim();
					i++; // Skip the code line
				}
			}

			stackFrames.push(frame);
			i++;
			continue;
		}

		// Try to match error type and message
		const errorMatch = line.match(TRACEBACK_PATTERNS.errorTypeMessage);
		if (errorMatch) {
			errorType = errorMatch[1];
			errorMessage = errorMatch[2];
			tracebackEndIndex = i;
			isComplete = true;
			break;
		}

		// Try to match standalone error type
		const errorTypeMatch = line.match(TRACEBACK_PATTERNS.errorTypeOnly);
		if (errorTypeMatch && !line.startsWith(' ')) {
			errorType = errorTypeMatch[1];
			tracebackEndIndex = i;
			isComplete = true;
			break;
		}

		// Check if this line looks like non-traceback output
		if (!line.startsWith(' ') && line.includes(':') && line.trim() !== '') {
			// This might be new output that's not part of the traceback
			// Check if the next line is also not indented
			if (i + 1 < lines.length) {
				const nextLine = lines[i + 1];
				if (!nextLine.startsWith(' ') && nextLine.trim() !== '') {
					tracebackEndIndex = i - 1;
					break;
				}
			}
		}

		i++;
	}

	// If we didn't find a clear error line, the traceback might be incomplete
	if (!isComplete && stackFrames.length > 0) {
		tracebackEndIndex = Math.min(tracebackEndIndex, lines.length - 1);
	}

	// Extract the final traceback text
	const tracebackLines = lines.slice(0, tracebackEndIndex + 1);
	const traceback = tracebackLines.join('\n').trim();

	if (!traceback || stackFrames.length === 0) {
		return null;
	}

	return {
		traceback,
		errorType,
		errorMessage,
		stackFrames,
		isComplete
	};
}

/**
 * Format traceback information for LLM context
 */
export function formatTracebackForLLM(tracebackInfo: TracebackInfo): string {
	if (!tracebackInfo) {
		return '';
	}

	let formatted = `=== PYTHON TRACEBACK ===\n`;
	formatted += `${tracebackInfo.traceback}\n`;

	if (tracebackInfo.errorType || tracebackInfo.errorMessage) {
		formatted += `\n=== ERROR ANALYSIS ===\n`;
		if (tracebackInfo.errorType) {
			formatted += `Error Type: ${tracebackInfo.errorType}\n`;
		}
		if (tracebackInfo.errorMessage) {
			formatted += `Error Message: ${tracebackInfo.errorMessage}\n`;
		}
	}

	if (tracebackInfo.stackFrames.length > 0) {
		formatted += `\n=== STACK FRAMES ===\n`;
		tracebackInfo.stackFrames.forEach((frame, index) => {
			formatted += `Frame ${index + 1}: ${frame.file}:${frame.line}`;
			if (frame.function) {
				formatted += ` in ${frame.function}`;
			}
			if (frame.code) {
				formatted += `\n  Code: ${frame.code}`;
			}
			formatted += '\n';
		});
	}

	formatted += `\nTraceback Complete: ${tracebackInfo.isComplete ? 'Yes' : 'No'}\n`;

	return formatted;
}

/**
 * Check if the given text contains what looks like a Python traceback
 */
export function containsTraceback(text: string): boolean {
	if (!text || typeof text !== 'string') {
		return false;
	}

	return TRACEBACK_KEYWORDS.some(keyword => text.includes(keyword));
}

/**
 * Extract just the error message from a traceback
 */
export function extractErrorMessage(tracebackInfo: TracebackInfo): string {
	if (!tracebackInfo) {
		return '';
	}

	if (tracebackInfo.errorMessage) {
		return tracebackInfo.errorMessage;
	}

	if (tracebackInfo.errorType) {
		return tracebackInfo.errorType;
	}

	// Fall back to last line of traceback
	const lines = tracebackInfo.traceback.split('\n');
	const lastLine = lines[lines.length - 1]?.trim();
	return lastLine || '';
}