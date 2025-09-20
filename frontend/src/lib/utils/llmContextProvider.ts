/**
 * LLM Context Provider for Python Console Integration
 *
 * This module provides structured context data from the Python console
 * for enhanced LLM assistant capabilities, including traceback analysis
 * and code context.
 */

import { pythonConsoleStore } from '$lib/stores/pythonConsole';
import type { TracebackInfo } from './tracebackExtractor';
import { get } from 'svelte/store';

export interface PythonConsoleContext {
	/** Current Python code in the editor */
	currentCode: string;
	/** Recent console output */
	recentOutput: string[];
	/** Structured traceback information if available */
	traceback: TracebackInfo | null;
	/** Formatted traceback for LLM consumption */
	formattedTraceback: string;
	/** Full console output history */
	fullOutput: string;
	/** Current cursor position */
	cursorPosition: { line: number; ch: number };
	/** Whether code is currently running */
	isExecuting: boolean;
	/** Last execution error (raw) */
	lastError: string | null;
}

export interface LLMContextOptions {
	/** Include full console output history */
	includeFullOutput?: boolean;
	/** Maximum lines of recent output to include */
	maxRecentOutputLines?: number;
	/** Include detailed traceback analysis */
	includeTracebackAnalysis?: boolean;
	/** Include code context around cursor */
	includeCodeContext?: boolean;
}

const defaultOptions: LLMContextOptions = {
	includeFullOutput: false,
	maxRecentOutputLines: 20,
	includeTracebackAnalysis: true,
	includeCodeContext: true
};

/**
 * Extract comprehensive context from the Python console for LLM interaction
 */
export function getPythonConsoleContext(options: LLMContextOptions = {}): PythonConsoleContext {
	const opts = { ...defaultOptions, ...options };
	const state = get(pythonConsoleStore);

	// Get recent output lines
	const recentOutput = opts.maxRecentOutputLines
		? state.output.slice(-opts.maxRecentOutputLines)
		: state.output;

	// Get formatted traceback if available
	const formattedTraceback = state.lastTraceback
		? pythonConsoleStore.getFormattedTraceback()
		: '';

	// Get full output if requested
	const fullOutput = opts.includeFullOutput
		? pythonConsoleStore.getFullOutput()
		: state.output.join('\n');

	return {
		currentCode: state.code,
		recentOutput,
		traceback: state.lastTraceback,
		formattedTraceback,
		fullOutput,
		cursorPosition: state.cursor,
		isExecuting: state.isRunning,
		lastError: state.lastError
	};
}

/**
 * Format Python console context for LLM prompt inclusion
 */
export function formatContextForLLM(
	context: PythonConsoleContext,
	options: LLMContextOptions = {}
): string {
	const opts = { ...defaultOptions, ...options };
	let formatted = '';

	// Add current code section
	if (context.currentCode.trim()) {
		formatted += '=== CURRENT PYTHON CODE ===\n';
		formatted += '```python\n';
		formatted += context.currentCode;
		formatted += '\n```\n\n';
	}

	// Add cursor position context
	if (opts.includeCodeContext && context.cursorPosition) {
		formatted += '=== CURSOR POSITION ===\n';
		formatted += `Line: ${context.cursorPosition.line + 1}, Column: ${context.cursorPosition.ch + 1}\n\n`;
	}

	// Add execution status
	if (context.isExecuting) {
		formatted += '=== EXECUTION STATUS ===\n';
		formatted += 'Python code is currently executing...\n\n';
	}

	// Add traceback analysis if available
	if (opts.includeTracebackAnalysis && context.traceback && context.formattedTraceback) {
		formatted += context.formattedTraceback + '\n\n';
	} else if (context.lastError) {
		formatted += '=== LAST ERROR ===\n';
		formatted += context.lastError + '\n\n';
	}

	// Add recent console output
	if (context.recentOutput.length > 0) {
		formatted += '=== RECENT CONSOLE OUTPUT ===\n';
		formatted += context.recentOutput.join('\n') + '\n\n';
	}

	// Add full output if requested and different from recent
	if (opts.includeFullOutput && context.fullOutput && context.fullOutput !== context.recentOutput.join('\n')) {
		formatted += '=== FULL CONSOLE HISTORY ===\n';
		formatted += context.fullOutput + '\n\n';
	}

	return formatted.trim();
}

/**
 * Create a focused context for error analysis and debugging
 */
export function getErrorAnalysisContext(): string {
	const context = getPythonConsoleContext({
		includeTracebackAnalysis: true,
		includeCodeContext: true,
		maxRecentOutputLines: 10
	});

	if (!context.traceback && !context.lastError) {
		return 'No recent errors or tracebacks available.';
	}

	let analysis = '=== ERROR ANALYSIS REQUEST ===\n\n';

	if (context.traceback) {
		analysis += context.formattedTraceback + '\n\n';

		// Add specific analysis sections
		if (context.traceback.stackFrames.length > 0) {
			analysis += '=== RELEVANT CODE SECTIONS ===\n';
			context.traceback.stackFrames.forEach((frame, index) => {
				if (frame.file.includes('inspector_code.py') || frame.file.includes('<string>')) {
					analysis += `Frame ${index + 1} (User Code): Line ${frame.line}\n`;
					if (frame.code) {
						analysis += `  Code: ${frame.code}\n`;
					}
				}
			});
			analysis += '\n';
		}
	}

	// Add current code for context
	if (context.currentCode.trim()) {
		analysis += '=== CURRENT CODE (for reference) ===\n';
		analysis += '```python\n';
		analysis += context.currentCode;
		analysis += '\n```\n\n';
	}

	analysis += '=== ANALYSIS REQUEST ===\n';
	analysis += 'Please analyze this error and provide:\n';
	analysis += '1. Root cause explanation\n';
	analysis += '2. Specific line(s) causing the issue\n';
	analysis += '3. Suggested fix or solution\n';
	analysis += '4. Prevention strategies for similar errors\n';

	return analysis;
}

/**
 * Create context for code completion and suggestions
 */
export function getCodeCompletionContext(cursorLine?: number): string {
	const context = getPythonConsoleContext({
		includeTracebackAnalysis: false,
		includeCodeContext: true,
		maxRecentOutputLines: 5
	});

	let completionContext = '=== CODE COMPLETION REQUEST ===\n\n';

	if (context.currentCode.trim()) {
		completionContext += '=== CURRENT CODE ===\n';
		completionContext += '```python\n';
		completionContext += context.currentCode;
		completionContext += '\n```\n\n';
	}

	if (cursorLine !== undefined) {
		const lines = context.currentCode.split('\n');
		const targetLine = lines[cursorLine];
		if (targetLine !== undefined) {
			completionContext += `=== CURSOR CONTEXT ===\n`;
			completionContext += `Current line ${cursorLine + 1}: "${targetLine}"\n\n`;
		}
	}

	if (context.recentOutput.length > 0) {
		completionContext += '=== RECENT OUTPUT ===\n';
		completionContext += context.recentOutput.slice(-3).join('\n') + '\n\n';
	}

	completionContext += '=== REQUEST ===\n';
	completionContext += 'Please suggest code completions, improvements, or next steps based on the current context.\n';

	return completionContext;
}

/**
 * Check if there are any errors that need attention
 */
export function hasRecentErrors(): boolean {
	const state = get(pythonConsoleStore);
	return !!(state.lastError || state.lastTraceback);
}

/**
 * Get a summary of the current Python console state
 */
export function getConsoleSummary(): string {
	const state = get(pythonConsoleStore);

	let summary = 'Python Console Status:\n';
	summary += `- Code lines: ${state.code.split('\n').length}\n`;
	summary += `- Output lines: ${state.output.length}\n`;
	summary += `- Has errors: ${hasRecentErrors() ? 'Yes' : 'No'}\n`;
	summary += `- Currently running: ${state.isRunning ? 'Yes' : 'No'}\n`;

	if (state.lastTraceback) {
		summary += `- Last error: ${state.lastTraceback.errorType || 'Unknown'}\n`;
		summary += `- Stack frames: ${state.lastTraceback.stackFrames.length}\n`;
	}

	return summary;
}