<script lang="ts">
	import { multiSelectMode, multiSelectedNodes } from '$lib/stores/uiagent';

	// Clear all selections when disabling multi-select mode
	function toggleMultiSelect() {
		if ($multiSelectMode) {
			// If currently enabled, disable and clear selections
			multiSelectMode.set(false);
			multiSelectedNodes.set([]);
		} else {
			// Enable multi-select mode
			multiSelectMode.set(true);
		}
	}
</script>

<style>
	.multi-select-toggle {
		background: var(--bg-secondary);
		border: 1px solid var(--border-color);
		color: var(--text-primary);
		border-radius: 4px;
		padding: 0.375rem 0.75rem;
		font-size: 0.875rem;
		cursor: pointer;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		gap: 0.375rem;
		white-space: nowrap;
	}

	.multi-select-toggle:hover {
		background: var(--bg-hover);
		border-color: var(--accent-color);
	}

	.multi-select-toggle.active {
		background: rgba(255, 165, 0, 0.2);
		border-color: #ffa500;
		color: #ffa500;
	}

	.multi-select-toggle.active:hover {
		background: rgba(255, 165, 0, 0.3);
	}

	.toggle-icon {
		font-size: 1em;
		display: flex;
		align-items: center;
	}

	.element-count {
		background: rgba(255, 255, 255, 0.1);
		padding: 0.1rem 0.4rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: bold;
		min-width: 1.2rem;
		text-align: center;
	}

	.active .element-count {
		background: rgba(0, 0, 0, 0.2);
		color: #ffa500;
	}
</style>

<button
	class="multi-select-toggle"
	class:active={$multiSelectMode}
	on:click={toggleMultiSelect}
	title={$multiSelectMode
		? `Multi-select ON (${$multiSelectedNodes.length} elements selected)`
		: 'Enable multi-select mode (Ctrl+Click to select multiple elements)'
	}
>
	<span class="toggle-icon">
		{$multiSelectMode ? '☑️' : '☐'}
	</span>
	<span>Multi-Select</span>
	{#if $multiSelectMode}
		<span class="element-count">{$multiSelectedNodes.length}</span>
	{/if}
</button>