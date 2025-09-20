<script lang="ts">
	export let handleRefresh: () => Promise<void>;
	export let interactionMode: 'navigate' | 'select';
	export let isRefreshing: boolean;

	// Default to 'select' (inspect mode), toggle to 'navigate' (interact mode)
	function toggleInteractionMode() {
		interactionMode = interactionMode === 'select' ? 'navigate' : 'select';
	}
</script>

<style>
	.control-button {
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

	.control-button:hover {
		background: var(--bg-hover);
		border-color: var(--accent-color);
	}

	.control-button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.interact-mode {
		background: rgba(255, 165, 0, 0.2);
		border-color: #ffa500;
		color: #ffa500;
	}

	.interact-mode:hover {
		background: rgba(255, 165, 0, 0.3);
	}

	.refresh-button.loading {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
</style>

<!-- Inline controls - no wrapper div -->
<button
	class="control-button"
	class:interact-mode={interactionMode === 'navigate'}
	on:click={toggleInteractionMode}
	title="{interactionMode === 'select' ? 'Click to enable Interact Mode (clicks will control device)' : 'Click to return to Inspect Mode (clicks only select elements)'}"
>
	{interactionMode === 'select' ? '👁️' : '👆'} {interactionMode === 'select' ? 'Inspect' : 'Interact'}
</button>

<button
	class="control-button refresh-button"
	class:loading={isRefreshing}
	on:click={handleRefresh}
	disabled={isRefreshing}
	title="Refresh Screenshot & Hierarchy (Ctrl+R)"
>
	{isRefreshing ? '⟳' : '🔄'} Refresh
</button>