<script lang="ts">
	import { multiSelectedNodes, selectedNode, multiSelectMode, type NodeInfo } from '$lib/stores/uiagent';

	// Remove an element from the selection
	function removeElement(element: NodeInfo) {
		multiSelectedNodes.update(nodes => {
			const newNodes = nodes.filter(n => n.key !== element.key);

			// If we removed the currently selected node, select the last remaining one
			if ($selectedNode?.key === element.key) {
				selectedNode.set(newNodes.length > 0 ? newNodes[newNodes.length - 1] : null);
			}

			return newNodes;
		});
	}

	// Clear all selected elements
	function clearAll() {
		multiSelectedNodes.set([]);
		selectedNode.set(null);
	}

	// Select an element (make it the primary selection)
	function selectElement(element: NodeInfo) {
		selectedNode.set(element);
	}

	// Get displayable text for an element
	function getElementDisplayText(element: NodeInfo): string {
		const props = element.properties;
		if (props?.text && props.text.trim()) {
			return props.text.trim();
		}
		if (props?.['content-desc'] && props['content-desc'].trim()) {
			return props['content-desc'].trim();
		}
		if (props?.['resource-id']) {
			const parts = props['resource-id'].split('/');
			return parts[parts.length - 1] || props['resource-id'];
		}
		return element.name.split('.').pop() || element.name;
	}

	// Get element type for display
	function getElementType(element: NodeInfo): string {
		return element.name.split('.').pop() || element.name;
	}

	// Get unique identifier for display
	function getElementId(element: NodeInfo): string | null {
		const resourceId = element.properties?.['resource-id'];
		if (resourceId) {
			const parts = resourceId.split('/');
			return parts[parts.length - 1] || resourceId;
		}
		return null;
	}
</script>

<style>
	.selected-elements-panel {
		background: #1e1e1e;
		border: 1px solid #333;
		border-radius: 6px;
		max-height: 300px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 0.75rem;
		background: #252526;
		border-bottom: 1px solid #333;
		font-size: 0.85rem;
		font-weight: bold;
		color: #ddd;
	}

	.clear-button {
		background: #e53935;
		border: none;
		color: white;
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
		font-size: 0.75rem;
		cursor: pointer;
		transition: background 0.2s ease;
	}

	.clear-button:hover {
		background: #c62828;
	}

	.clear-button:disabled {
		background: #555;
		cursor: not-allowed;
	}

	.elements-list {
		flex: 1;
		overflow-y: auto;
		padding: 0.25rem;
		max-height: 240px;
	}

	.element-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.5rem;
		border-radius: 4px;
		border: 1px solid transparent;
		margin-bottom: 0.25rem;
		cursor: pointer;
		transition: all 0.2s ease;
		position: relative;
	}

	.element-item:hover {
		background: rgba(255, 255, 255, 0.05);
		border-color: #555;
	}

	.element-item.selected {
		background: rgba(0, 120, 255, 0.2);
		border-color: rgba(0, 120, 255, 0.5);
	}

	.element-checkbox {
		flex-shrink: 0;
		width: 16px;
		height: 16px;
		background: #333;
		border: 1px solid #555;
		border-radius: 3px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		color: #00ff00;
	}

	.element-info {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.element-text {
		font-size: 0.8rem;
		color: #fff;
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.element-meta {
		display: flex;
		gap: 0.5rem;
		font-size: 0.7rem;
		color: #888;
	}

	.element-type {
		color: #92c9ff;
	}

	.element-id {
		color: #ffa500;
	}

	.remove-button {
		flex-shrink: 0;
		background: #e53935;
		border: none;
		color: white;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		font-size: 12px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.2s ease;
		opacity: 0.7;
	}

	.remove-button:hover {
		background: #c62828;
		opacity: 1;
	}

	.empty-state {
		padding: 1rem;
		text-align: center;
		color: #888;
		font-size: 0.85rem;
		font-style: italic;
	}

	/* Scrollbar styling */
	.elements-list::-webkit-scrollbar {
		width: 6px;
	}

	.elements-list::-webkit-scrollbar-track {
		background: #2a2a2a;
		border-radius: 3px;
	}

	.elements-list::-webkit-scrollbar-thumb {
		background: #555;
		border-radius: 3px;
	}

	.elements-list::-webkit-scrollbar-thumb:hover {
		background: #777;
	}
</style>

{#if $multiSelectMode}
	<div class="selected-elements-panel">
		<div class="panel-header">
			<span>Selected Elements ({$multiSelectedNodes.length})</span>
			<button
				class="clear-button"
				on:click={clearAll}
				disabled={$multiSelectedNodes.length === 0}
				title="Clear all selected elements"
			>
				Clear All
			</button>
		</div>

		<div class="elements-list">
			{#if $multiSelectedNodes.length === 0}
				<div class="empty-state">
					No elements selected.<br>
					Hold Ctrl/Cmd and click elements to select them.
				</div>
			{:else}
				{#each $multiSelectedNodes as element (element.key)}
					<div
						class="element-item"
						class:selected={$selectedNode?.key === element.key}
						on:click={() => selectElement(element)}
						on:keydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								e.preventDefault();
								selectElement(element);
							}
						}}
						title="Click to make this the primary selection"
						role="button"
						tabindex="0"
					>
						<div class="element-checkbox">✓</div>

						<div class="element-info">
							<div class="element-text">
								{getElementDisplayText(element)}
							</div>
							<div class="element-meta">
								<span class="element-type">{getElementType(element)}</span>
								{#if getElementId(element)}
									<span class="element-id">#{getElementId(element)}</span>
								{/if}
							</div>
						</div>

						<button
							class="remove-button"
							on:click|stopPropagation={() => removeElement(element)}
							title="Remove from selection"
						>
							×
						</button>
					</div>
				{/each}
			{/if}
		</div>
	</div>
{/if}