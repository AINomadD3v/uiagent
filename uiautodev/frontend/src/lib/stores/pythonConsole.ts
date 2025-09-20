/**
 * @file This custom Svelte store manages the complete state for the Python Console.
 * It bundles the state (code, output, etc.) and actions that can modify that state,
 * creating a self-contained and reusable module for the console's logic.
 * This version uses an action-based system for editor modifications, which is more
 * robust and suitable for an autonomous agent.
 */

import { writable, get } from 'svelte/store';
import type { InteractiveResponse } from '$lib/api/types';
import { executeInteractivePython } from '$lib/api/pythonClient';
import { extractTraceback, formatTracebackForLLM, type TracebackInfo } from '$lib/utils/tracebackExtractor';

// ─── DATA STRUCTURES ────────────────────────────────────────────────────────────────────────────

/**
 * Defines the payload for a 'REPLACE_BLOCK' action. This is dispatched from
 * the LLM Assistant and handled by the CodeEditorWrapper.
 */
export interface ReplaceActionPayload {
	type: 'REPLACE_BLOCK';
	start_line: number;
	end_line: number;
	code: string;
}

/** Defines the shape of the data managed by the python console store. */
export interface PythonConsoleState {
	/** The current Python code in the editor. */
	code: string;
	/** An array of accumulated output lines from executed code. */
	output: string[];
	/** The most recent traceback string, if an error occurred. */
	lastError: string | null;
	/** Structured traceback information for LLM integration. */
	lastTraceback: TracebackInfo | null;
	/** Full accumulated console output for LLM context. */
	fullOutput: string;
	/** Controls the visibility of the console's output panel. */
	isOpen: boolean;
	/** Whether code is currently executing. */
	isRunning: boolean;
	/** The editor's last known cursor position. */
	cursor: { line: number; ch: number };
	/**
	 * ✅ The new action channel. When a component dispatches an action, this property
	 * is updated. The CodeEditorWrapper listens to this and performs the required
	 * editor modification. We add a random ID to ensure Svelte detects the object change.
	 */
	lastAction: (ReplaceActionPayload & { id: number }) | null;
}

/** The default state for the console when the application first loads. */
const initialState: PythonConsoleState = {
	code: `# Write Python here.\n# Use Vim keys, Ctrl-Space for completions.\nprint("Hello UIAgent")\n`,
	output: [],
	lastError: null,
	lastTraceback: null,
	fullOutput: '',
	isOpen: false,
	isRunning: false,
	cursor: { line: 0, ch: 0 },
	lastAction: null // Initially, there is no action to perform.
};

/** Factory function that creates the custom store object. */
function createPythonConsoleStore() {
	const { subscribe, update, set } = writable<PythonConsoleState>({ ...initialState });

	return {
		/** Allows Svelte components to subscribe to state changes. */
		subscribe,

		// --- NEW ACTION-BASED METHOD ---
		/**
		 * Dispatches a 'REPLACE_BLOCK' action to be handled by the editor.
		 * This is the new, primary way the LLM agent will modify code.
		 */
		dispatchReplaceAction: (payload: Omit<ReplaceActionPayload, 'type'>) =>
			update((s) => {
				s.lastAction = { ...payload, type: 'REPLACE_BLOCK', id: Math.random() };
				return s;
			}),

		/** Updates the code in the store. Primarily called by the editor component on user input. */
		setCode: (newCode: string) =>
			update((s) => {
				s.code = newCode;
				return s;
			}),

		/** Updates the cursor position in the store. */
		setCursor: (pos: { line: number; ch: number }) =>
			update((s) => {
				s.cursor = pos;
				return s;
			}),

		/** Clears all console output and the stored error message. */
		clearOutput: () =>
			update((s) => {
				s.output = [];
				s.lastError = null;
				s.lastTraceback = null;
				s.fullOutput = '';
				return s;
			}),

		/** Appends new lines to the console output and extracts tracebacks. */
		appendOutput: (text: string) =>
			update((s) => {
				const lines = text.split(/\r?\n/).filter((l) => l !== '');
				s.output = [...s.output, ...lines];

				// Update full output for LLM context
				s.fullOutput += (s.fullOutput ? '\n' : '') + text;

				// Extract traceback information
				const tracebackInfo = extractTraceback(text);
				if (tracebackInfo) {
					s.lastTraceback = tracebackInfo;
					s.lastError = tracebackInfo.traceback;
				}

				return s;
			}),

		/** Stores the last error traceback for the LLM to potentially use as context. */
		setLastError: (err: string) =>
			update((s) => {
				s.lastError = err;
				// Also try to extract traceback information
				const tracebackInfo = extractTraceback(err);
				if (tracebackInfo) {
					s.lastTraceback = tracebackInfo;
				}
				return s;
			}),

		/** Get the last traceback for LLM integration. */
		getLastTraceback: () => {
			const state = get({ subscribe });
			return state.lastTraceback;
		},

		/** Get formatted traceback for LLM context. */
		getFormattedTraceback: () => {
			const state = get({ subscribe });
			return state.lastTraceback ? formatTracebackForLLM(state.lastTraceback) : '';
		},

		/** Get full console output for LLM context. */
		getFullOutput: () => {
			const state = get({ subscribe });
			return state.fullOutput;
		},

		/** Controls the visibility of the console's output panel. */
		open: () => update((s) => ((s.isOpen = true), s)),
		close: () => update((s) => ((s.isOpen = false), s)),
		toggleOpen: () => update((s) => ((s.isOpen = !s.isOpen), s)),

		/** Sets the running state of the console. */
		setIsRunning: (running: boolean) =>
			update((s) => {
				s.isRunning = running;
				return s;
			}),

		/** Executes the current code in the editor via the backend API. */
		executeInteractive: async (
			serial: string,
			enableTracing: boolean = false
		): Promise<InteractiveResponse> => {
			try {
				update((s) => {
					s.isRunning = true;
					return s;
				});

				const { code } = get({ subscribe });
				const resp = await executeInteractivePython(serial, code, enableTracing);
				return resp;
			} finally {
				update((s) => {
					s.isRunning = false;
					return s;
				});
			}
		},

		/** Resets the entire store back to its default state. */
		reset: () => set({ ...initialState })
	};
}

/** The singleton instance of the python console store, exported for use in any component. */
export const pythonConsoleStore = createPythonConsoleStore();

