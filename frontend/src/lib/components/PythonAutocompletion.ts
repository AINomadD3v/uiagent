/**
 * Advanced Python Autocompletion Extension for CodeMirror 6
 *
 * This module implements sophisticated Python autocompletion with:
 * - Backend integration via completion API
 * - Request debouncing and cancellation
 * - Auto-trigger on dot keypress
 * - Smart cursor positioning for functions
 * - Parameter hints support
 */

import {
	autocompletion,
	startCompletion,
	closeCompletion,
	type CompletionContext,
	type CompletionResult,
	type Completion
} from '@codemirror/autocomplete';
import { keymap } from '@codemirror/view';
import { type Extension } from '@codemirror/state';
import { getPythonCompletions } from '$lib/api/pythonClient';
import type { PythonCompletionSuggestion } from '$lib/api/types';

/**
 * Global completion controller for request cancellation
 */
let completionController: AbortController | null = null;

/**
 * Debounce timer for completion requests
 */
let debounceTimer: number | null = null;

/**
 * Configuration for the Python completion system
 */
interface PythonCompletionConfig {
	debounceMs: number;
	enableAutoTrigger: boolean;
	enableDotTrigger: boolean;
}

const defaultConfig: PythonCompletionConfig = {
	debounceMs: 300,
	enableAutoTrigger: true,
	enableDotTrigger: true
};

/**
 * Main Python completion function that interfaces with the backend
 */
async function pythonCompletionSource(
	context: CompletionContext,
	config: PythonCompletionConfig = defaultConfig
): Promise<CompletionResult | null> {
	const { state, pos } = context;
	const doc = state.doc;
	const line = doc.lineAt(pos);
	const lineText = line.text;
	const column = pos - line.from;
	const lineNumber = doc.lineAt(pos).number - 1; // Convert to 0-based
	const fullCode = doc.toString();

	// Get current token information
	const beforeCursor = lineText.slice(0, column);
	const afterCursor = lineText.slice(column);

	// Determine if we should trigger completion
	const wordMatch = beforeCursor.match(/[a-zA-Z_][a-zA-Z0-9_]*$/);
	const isDotTrigger = beforeCursor.endsWith('.');
	const isEmptyAfterDot = beforeCursor.match(/\.\s*$/);

	// Don't complete in certain contexts
	if (!wordMatch && !isDotTrigger && !isEmptyAfterDot) {
		return null;
	}

	// Cancel any pending completion request
	if (completionController) {
		completionController.abort();
	}
	completionController = new AbortController();

	try {
		// Make backend completion request
		const suggestions = await getPythonCompletions({
			code: fullCode,
			line: lineNumber,
			column: column
		}, completionController.signal);

		if (!suggestions || suggestions.length === 0) {
			return null;
		}

		// Calculate completion range
		let from = pos;
		let to = pos;

		if (isDotTrigger || isEmptyAfterDot) {
			// For dot triggers, insert at current position
			from = pos;
			to = pos;
		} else if (wordMatch) {
			// For word completions, replace the partial word
			from = pos - wordMatch[0].length;
			to = pos;

			// Extend 'to' to include rest of word if cursor is in middle
			const restOfWord = afterCursor.match(/^[a-zA-Z0-9_]*/);
			if (restOfWord) {
				to = pos + restOfWord[0].length;
			}
		}

		// Convert backend suggestions to CodeMirror format
		const completions: Completion[] = suggestions.map((suggestion: PythonCompletionSuggestion) => {
			const completion: Completion = {
				label: suggestion.displayText || suggestion.text,
				type: suggestion.type || 'variable',
				info: suggestion.type,
				apply: (view, completion, from, to) => {
					// Smart cursor positioning for function calls
					if (suggestion.text.includes('(') && !suggestion.text.endsWith(')')) {
						// Insert the completion
						view.dispatch({
							changes: { from, to, insert: suggestion.text }
						});

						// Position cursor inside parentheses
						const insertedText = suggestion.text;
						const openParenIndex = insertedText.lastIndexOf('(');
						if (openParenIndex !== -1) {
							const cursorPos = from + openParenIndex + 1;
							view.dispatch({
								selection: { anchor: cursorPos, head: cursorPos }
							});
						}
					} else {
						// Standard completion insertion
						view.dispatch({
							changes: { from, to, insert: suggestion.text }
						});
					}
				}
			};
			return completion;
		});

		return {
			from,
			to,
			options: completions,
			filter: false // We handle filtering on the backend
		};

	} catch (error: any) {
		if (error.name === 'AbortError') {
			// Request was cancelled, this is normal
			return null;
		}
		console.error('Python completion error:', error);
		return null;
	}
}

/**
 * Debounced wrapper for the completion source
 */
function debouncedCompletionSource(
	config: PythonCompletionConfig = defaultConfig
) {
	return (context: CompletionContext): Promise<CompletionResult | null> => {
		return new Promise((resolve) => {
			// Clear existing timer
			if (debounceTimer !== null) {
				clearTimeout(debounceTimer);
			}

			// Set new debounced timer
			debounceTimer = window.setTimeout(async () => {
				const result = await pythonCompletionSource(context, config);
				resolve(result);
			}, config.debounceMs);
		});
	};
}

/**
 * Custom keymap for Python-specific shortcuts
 */
const pythonKeymaps = keymap.of([
	{
		key: 'Ctrl-Space',
		run: (view) => {
			startCompletion(view);
			return true;
		}
	},
	{
		key: 'Shift-Ctrl-Space',
		run: (view) => {
			// Parameter hints - trigger completion but show only function signatures
			startCompletion(view);
			return true;
		}
	},
	{
		key: 'Escape',
		run: (view) => {
			closeCompletion(view);
			return false; // Allow other escape handlers
		}
	}
]);

/**
 * Auto-trigger completion on dot keypress
 */
const dotTriggerKeymap = keymap.of([
	{
		key: '.',
		run: (view) => {
			// Insert the dot first
			view.dispatch({
				changes: {
					from: view.state.selection.main.head,
					insert: '.'
				},
				selection: {
					anchor: view.state.selection.main.head + 1
				}
			});

			// Trigger completion after a short delay
			setTimeout(() => {
				startCompletion(view);
			}, 50);

			return true;
		}
	}
]);

/**
 * Main extension factory for Python autocompletion
 */
export function pythonAutocompletion(config: Partial<PythonCompletionConfig> = {}): Extension {
	const finalConfig = { ...defaultConfig, ...config };

	const extensions: Extension[] = [
		autocompletion({
			override: [debouncedCompletionSource(finalConfig)],
			maxRenderedOptions: 20,
			closeOnBlur: true,
			activateOnTyping: finalConfig.enableAutoTrigger,
			interactionDelay: finalConfig.debounceMs
		}),
		pythonKeymaps
	];

	// Add dot trigger if enabled
	if (finalConfig.enableDotTrigger) {
		extensions.push(dotTriggerKeymap);
	}

	return extensions;
}

/**
 * Cleanup function to cancel any pending requests
 */
export function cleanupPythonCompletion(): void {
	if (completionController) {
		completionController.abort();
		completionController = null;
	}

	if (debounceTimer !== null) {
		clearTimeout(debounceTimer);
		debounceTimer = null;
	}
}