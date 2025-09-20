<script lang="ts">
	import { multiSelectedNodes, multiSelectMode, type NodeInfo } from '$lib/stores/uiagent';

	export let element: NodeInfo;
	export let size: 'small' | 'medium' | 'large' = 'medium';

	$: isSelected = $multiSelectedNodes.some(node => node.key === element.key);

	function toggleSelection() {
		if (!$multiSelectMode) return;

		multiSelectedNodes.update(nodes => {
			const index = nodes.findIndex(n => n.key === element.key);
			if (index >= 0) {
				// Remove if already selected
				const newNodes = [...nodes];
				newNodes.splice(index, 1);
				return newNodes;
			} else {
				// Add if not selected
				return [...nodes, element];
			}
		});
	}
</script>

<style>
	.element-checkbox {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 1px solid #555;
		border-radius: 3px;
		cursor: pointer;
		transition: all 0.2s ease;
		background: #333;
		position: relative;
		flex-shrink: 0;
	}

	.element-checkbox:hover {
		border-color: #777;
		background: #444;
	}

	.element-checkbox.selected {
		background: #ffa500;
		border-color: #ff8c00;
		color: #000;
	}

	.element-checkbox.disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.element-checkbox.disabled:hover {
		border-color: #555;
		background: #333;
	}

	/* Size variants */
	.element-checkbox.small {
		width: 14px;
		height: 14px;
		font-size: 8px;
	}

	.element-checkbox.medium {
		width: 16px;
		height: 16px;
		font-size: 10px;
	}

	.element-checkbox.large {
		width: 20px;
		height: 20px;
		font-size: 12px;
	}

	.checkmark {
		font-weight: bold;
		line-height: 1;
		opacity: 0;
		transform: scale(0.5);
		transition: all 0.15s ease;
	}

	.selected .checkmark {
		opacity: 1;
		transform: scale(1);
	}
</style>

<div
	class="element-checkbox {size}"
	class:selected={isSelected}
	class:disabled={!$multiSelectMode}
	on:click={toggleSelection}
	title={$multiSelectMode
		? isSelected
			? 'Remove from selection'
			: 'Add to selection'
		: 'Enable multi-select mode to use checkboxes'
	}
	role="checkbox"
	tabindex={$multiSelectMode ? 0 : -1}
	aria-checked={isSelected}
	aria-disabled={!$multiSelectMode}
	on:keydown={(e) => {
		if ((e.key === 'Enter' || e.key === ' ') && $multiSelectMode) {
			e.preventDefault();
			toggleSelection();
		}
	}}
>
	<span class="checkmark">✓</span>
</div>