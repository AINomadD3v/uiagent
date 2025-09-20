<!-- Python Console with Integrated Resizable Output Panel
     Replicates the legacy system's resizable Python console output functionality -->

<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import CodeEditorWrapper from './CodeEditorWrapper.svelte';
	import ResizablePanel from './ResizablePanel.svelte';
	import { pythonConsoleStore } from '$lib/stores/pythonConsole';
	import { panelActions, pythonConsoleOutputPanel } from '$lib/stores/panelState';
	import { interruptExecution } from '$lib/api/pythonClient';

	// ─── Props ───────────────────────────────────────────────────────────────

	export let serial: string;

	// ─── State ──────────────────────────────────────────────────────────────

	let outputLines: string[] = [];
	let outputElement: HTMLDivElement;

	// Subscribe to console output changes
	$: outputLines = $pythonConsoleStore.output;

	// ─── Python Console Actions ─────────────────────────────────────────────

	async function runCode() {
		if (!browser || !serial) {
			alert('Please select a device first.');
			return;
		}

		// Open the output panel when running code
		panelActions.setOpen('python-console-output', true);

		pythonConsoleStore.clearOutput();
		pythonConsoleStore.appendOutput('⏳ Running script...');

		try {
			const data = await pythonConsoleStore.executeInteractive(serial);

			pythonConsoleStore.clearOutput();

			let out = '';
			if (data.stdout) out += data.stdout;
			if (data.result != null) out += `\n>>> ${data.result}\n`;
			if (data.stderr) out += `\n--- STDERR ---\n${data.stderr}`;
			if (data.execution_error) {
				out += `\n--- ERROR ---\n${data.execution_error}`;
				pythonConsoleStore.setLastError(data.execution_error);
			}

			pythonConsoleStore.appendOutput(out.trim() || '# (The script ran with no output)');
		} catch (e: any) {
			const errorMsg = `Error calling backend: ${e.message || e}`;
			pythonConsoleStore.clearOutput();
			pythonConsoleStore.appendOutput(errorMsg);
			pythonConsoleStore.setLastError(errorMsg);
		}
	}

	async function stopCode() {
		if (!browser || !serial) return;
		console.log('Attempting to stop script execution...');
		try {
			await interruptExecution(serial);
			pythonConsoleStore.appendOutput('\n⏹️ Execution stop request sent.');
			pythonConsoleStore.setIsRunning(false);
		} catch (e: any) {
			pythonConsoleStore.appendOutput(`\nFailed to send stop signal: ${e.message}`);
		}
	}

	// ─── Output Panel Actions ───────────────────────────────────────────────

	function toggleOutput() {
		panelActions.toggleOpen('python-console-output');
	}

	function clearOutput() {
		pythonConsoleStore.clearOutput();
	}

	// ─── Auto-scroll Output ─────────────────────────────────────────────────

	function scrollToBottom() {
		if (outputElement) {
			outputElement.scrollTop = outputElement.scrollHeight;
		}
	}

	$: if (outputLines.length > 0) {
		// Auto-scroll when new output is added
		setTimeout(scrollToBottom, 10);
	}

	// ─── Panel Resize Handler ────────────────────────────────────────────────

	function handleOutputResize() {
		// Trigger any necessary layout recalculations
		// This could include refreshing the code editor if needed
		if (browser && (window as any).PythonConsoleManager?.refresh) {
			setTimeout(() => {
				(window as any).PythonConsoleManager.refresh();
			}, 50);
		}
	}

	// ─── Lifecycle ──────────────────────────────────────────────────────────

	onMount(() => {
		// Initial setup - ensure panel state is initialized
		if (!panelActions.getPanel('python-console-output')) {
			panelActions.updateDimensions('python-console-output', {
				height: 150,
				minHeight: 60,
				maxHeight: 400
			});
		}
	});
</script>

<div class="python-console-container">
	<!-- Code Editor Area -->
	<div class="editor-section">
		<div class="editor-wrapper">
			<CodeEditorWrapper visible={true} />
		</div>

		<!-- Toolbar -->
		<div class="toolbar">
			{#if $pythonConsoleStore.isRunning}
				<button class="stop-button" on:click={stopCode}>⏹️ Stop Code</button>
			{:else}
				<button class="run-button" on:click={runCode}>▶️ Run Code</button>
			{/if}

			<button class="output-toggle" on:click={toggleOutput}>
				{#if $pythonConsoleOutputPanel?.isOpen}
					📄 Hide Output
				{:else}
					📄 Show Output
				{/if}
			</button>

			{#if $pythonConsoleOutputPanel?.isOpen}
				<button class="clear-button" on:click={clearOutput} title="Clear Output">
					🗑️ Clear
				</button>
			{/if}
		</div>
	</div>

	<!-- Resizable Output Panel -->
	{#if browser && $pythonConsoleOutputPanel}
		<ResizablePanel
			panelId="python-console-output"
			direction="vertical"
			isOpen={$pythonConsoleOutputPanel.isOpen}
			dimensions={$pythonConsoleOutputPanel.dimensions}
			dragHandlePosition="top"
			className="output-panel"
			on:resize={handleOutputResize}
		>
			<div class="output-content">
				<div class="output-header">
					<span class="output-title">Console Output</span>
					<div class="output-controls">
						<button
							class="output-control-btn"
							on:click={clearOutput}
							title="Clear Output"
							disabled={outputLines.length === 0}
						>
							Clear
						</button>
						<button
							class="output-control-btn"
							on:click={toggleOutput}
							title="Hide Output"
						>
							Hide
						</button>
					</div>
				</div>

				<div class="output-display" bind:this={outputElement}>
					{#if outputLines.length === 0}
						<div class="output-placeholder">
							# No output yet. Run some code to see the results.
						</div>
					{:else}
						{#each outputLines as line, index}
							<div class="output-line" class:error-line={line.includes('ERROR') || line.includes('STDERR')}>
								{line}
							</div>
						{/each}
					{/if}
				</div>
			</div>
		</ResizablePanel>
	{/if}
</div>

<style>
	.python-console-container {
		display: flex;
		flex-direction: column;
		height: 100%;
		width: 100%;
		background: #1e1e1e;
		overflow: hidden;
	}

	/* ─── Editor Section ─────────────────────────────────────────────────── */

	.editor-section {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}

	.editor-wrapper {
		flex: 1;
		position: relative;
		min-height: 0;
		background: #1e1e1e;
	}

	/* ─── Toolbar ────────────────────────────────────────────────────────── */

	.toolbar {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem;
		border-top: 1px solid #333;
		flex-shrink: 0;
		background: #252526;
		align-items: center;
	}

	.toolbar button {
		padding: 0.5rem 1rem;
		background: #3c3c3c;
		border: 1px solid #555;
		color: #ddd;
		border-radius: 5px;
		cursor: pointer;
		font-weight: 500;
		font-size: 0.9rem;
		transition: background-color 0.2s ease;
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}

	.toolbar button:hover {
		background: #4f4f4f;
	}

	.toolbar button:disabled {
		background: #2a2a2a;
		color: #666;
		cursor: not-allowed;
	}

	.run-button {
		background-color: #2d7d32;
		border-color: #4caf50;
	}

	.run-button:hover {
		background-color: #388e3c;
	}

	.stop-button {
		background-color: #a13d3d;
		border-color: #c55a5a;
	}

	.stop-button:hover {
		background-color: #b84a4a;
	}

	.output-toggle {
		background-color: #1565c0;
		border-color: #1976d2;
	}

	.output-toggle:hover {
		background-color: #1976d2;
	}

	.clear-button {
		background-color: #bf360c;
		border-color: #d84315;
	}

	.clear-button:hover {
		background-color: #d84315;
	}

	/* ─── Output Panel ───────────────────────────────────────────────────── */

	:global(.output-panel) {
		border-top: 1px solid #333;
		border-radius: 0;
		background: #1a1a1a;
	}

	.output-content {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}

	.output-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem;
		border-bottom: 1px solid #333;
		background: #2a2a2a;
		flex-shrink: 0;
	}

	.output-title {
		font-weight: 600;
		font-size: 0.9rem;
		color: #ddd;
	}

	.output-controls {
		display: flex;
		gap: 0.5rem;
	}

	.output-control-btn {
		padding: 0.2rem 0.5rem;
		background: #3c3c3c;
		border: 1px solid #555;
		color: #ddd;
		border-radius: 3px;
		cursor: pointer;
		font-size: 0.8rem;
		transition: background-color 0.2s ease;
	}

	.output-control-btn:hover {
		background: #4f4f4f;
	}

	.output-control-btn:disabled {
		background: #2a2a2a;
		color: #666;
		cursor: not-allowed;
	}

	/* ─── Output Display ─────────────────────────────────────────────────── */

	.output-display {
		flex: 1;
		padding: 0.5rem;
		overflow-y: auto;
		font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
		font-size: 13px;
		background: #1a1a1a;
		color: #d4d4d4;
		scrollbar-width: thin;
		scrollbar-color: #555 #2a2a2a;
		line-height: 1.4;
	}

	.output-display::-webkit-scrollbar {
		width: 8px;
	}

	.output-display::-webkit-scrollbar-track {
		background: #2a2a2a;
	}

	.output-display::-webkit-scrollbar-thumb {
		background: #555;
		border-radius: 4px;
	}

	.output-display::-webkit-scrollbar-thumb:hover {
		background: #666;
	}

	.output-line {
		white-space: pre-wrap;
		word-break: break-word;
		margin-bottom: 0.1rem;
		min-height: 1.2em;
	}

	.output-line.error-line {
		color: #f48771;
		background: rgba(244, 135, 113, 0.1);
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		border-left: 3px solid #f48771;
	}

	.output-placeholder {
		color: #888;
		font-style: italic;
		padding: 1rem;
		text-align: center;
	}

	/* ─── Responsive Design ──────────────────────────────────────────────── */

	@media (max-width: 768px) {
		.toolbar {
			flex-wrap: wrap;
			gap: 0.3rem;
		}

		.toolbar button {
			padding: 0.4rem 0.8rem;
			font-size: 0.8rem;
		}

		.output-header {
			padding: 0.3rem;
		}

		.output-controls {
			gap: 0.3rem;
		}

		.output-control-btn {
			padding: 0.1rem 0.4rem;
			font-size: 0.7rem;
		}
	}

	/* ─── Accessibility ──────────────────────────────────────────────────── */

	@media (prefers-reduced-motion: reduce) {
		.toolbar button,
		.output-control-btn {
			transition: none;
		}
	}

	/* ─── High Contrast Mode ─────────────────────────────────────────────── */

	@media (prefers-contrast: high) {
		.output-line.error-line {
			border-left-width: 4px;
			background: rgba(244, 135, 113, 0.2);
		}

		.toolbar button,
		.output-control-btn {
			border-width: 2px;
		}
	}
</style>