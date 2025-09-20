<script lang="ts">
	// ─── Svelte Imports ──────────────────────────────────────────────────────────────────────────
	import { onMount, tick } from 'svelte';
	import { derived } from 'svelte/store';
	import type { NodeInfo } from '$lib/stores/uiagent';

	// ─── Stores ──────────────────────────────────────────────────────────────────────────────────
	import { selectedSerial, selectedNode } from '$lib/stores/uiagent';
	import { pythonConsoleStore } from '$lib/stores/pythonConsole'; // ✅ Import the console store
	import {
		hierarchy,
		isLoadingHierarchy,
		hierarchyError,
		refreshHierarchy
	} from '$lib/stores/hierarchy';
	import { notificationStore, updateMessage } from '$lib/stores/notifications'; // ✅ Import the notification system
	import { panelActions, leftPanel, middlePanel, hierarchyPanel } from '$lib/stores/panelState'; // ✅ Import panel state management

	// ─── Components ──────────────────────────────────────────────────────────────────────────────
	import DeviceSelectorPanel from '$lib/components/DeviceSelectorPanel.svelte';
	import DeviceScreenshot from '$lib/components/DeviceScreenshot.svelte';
	import LLMAssistant from '$lib/components/LLMAssistant.svelte';
	import PropertiesPanel from '$lib/components/PropertiesPanel.svelte';
	import PythonConsole from '$lib/components/PythonConsole.svelte';
	import PythonConsoleWithOutput from '$lib/components/PythonConsoleWithOutput.svelte';
	import HierarchyTree from '$lib/components/HierarchyTree.svelte';
	import ConsoleOutput from '$lib/components/ConsoleOutput.svelte'; // ✅ Import the new floating console
	import NotificationContainer from '$lib/components/NotificationContainer.svelte'; // ✅ Import the notification system
	import MultiSelectToggle from '$lib/components/MultiSelectToggle.svelte';
	import SelectedElementsList from '$lib/components/SelectedElementsList.svelte';
	import DeviceControls from '$lib/components/DeviceControls.svelte';

	// ─── Component State ─────────────────────────────────────────────────────────────────────────

	/** The active tab in the middle panel ('assistant' or 'details'). */
	let midTab: 'assistant' | 'details' = 'assistant';

	/** The active tab in the right panel ('python' or 'hierarchy'). */
	let rightTab: 'python' | 'hierarchy' = 'python';

	/** The search term entered by the user for filtering the UI hierarchy. */
	let hierarchySearchTerm = '';

	/** A Set containing the keys of all nodes that should be expanded in the tree. */
	let expandedKeys = new Set<string>();

	/** An array of node keys that match the current search term. */
	let searchMatches: string[] = [];

	// DeviceScreenshot component references
	let deviceScreenshotComponent: any;
	let deviceInteractionMode: 'navigate' | 'select' = 'select';
	let deviceIsRefreshing = false;

	/** The index of the currently highlighted search match. */
	let currentMatchIndex = -1;

	// Device control handlers
	async function handleDeviceRefresh() {
		if (deviceScreenshotComponent && deviceScreenshotComponent.handleRefresh) {
			await deviceScreenshotComponent.handleRefresh();
		}
	}

	// ─── Logic ───────────────────────────────────────────────────────────────────────────────────

	/**
	 * A helper function to determine if a node matches a given search term.
	 */
	function isNodeMatching(n: NodeInfo, term: string): boolean {
		const lowerCaseTerm = term.toLowerCase();
		if (n.name.toLowerCase().includes(lowerCaseTerm)) return true;
		if (n.properties) {
			for (const key in n.properties) {
				if (String(n.properties[key] ?? '').toLowerCase().includes(lowerCaseTerm)) {
					return true;
				}
			}
		}
		return false;
	}

	/**
	 * Helper function to find a node by its key from the root.
	 */
	function findNodeByKey(node: NodeInfo, key: string): NodeInfo | null {
		if (node.key === key) return node;
		for (const child of node.children) {
			const found = findNodeByKey(child, key);
			if (found) return found;
		}
		return null;
	}

	/**
	 * Reactive block to automatically expand the hierarchy and find search matches.
	 */
	$: if ($hierarchy) {
		if (!hierarchySearchTerm) {
			// Clear search results and expand all nodes
			const allKeys = new Set<string>();
			const expandAll = (n: NodeInfo) => {
				allKeys.add(n.key);
				n.children?.forEach(expandAll);
			};
			expandAll($hierarchy);
			expandedKeys = allKeys;
			searchMatches = [];
			currentMatchIndex = -1;
		} else {
			const matchingParentKeys = new Set<string>();
			const directMatches: string[] = [];

			const searchAndExpand = (node: NodeInfo, path: string[]): boolean => {
				const currentPath = [...path, node.key];
				let hasMatchingDescendant = false;

				for (const child of node.children) {
					if (searchAndExpand(child, currentPath)) {
						hasMatchingDescendant = true;
					}
				}

				const isDirectMatch = isNodeMatching(node, hierarchySearchTerm);
				if (isDirectMatch) {
					directMatches.push(node.key);
				}

				if (isDirectMatch || hasMatchingDescendant) {
					currentPath.forEach((key) => matchingParentKeys.add(key));
					return true;
				}
				return false;
			};

			searchAndExpand($hierarchy, []);
			expandedKeys = matchingParentKeys;
			searchMatches = directMatches;

			// If there are matches, select the first one automatically
			if (searchMatches.length > 0) {
				currentMatchIndex = 0;
				selectedNode.set(findNodeByKey($hierarchy, searchMatches[0]));
			} else {
				currentMatchIndex = -1;
			}
		}
	}

	/**
	 * Navigates to the next search match.
	 */
	function nextMatch() {
		if (searchMatches.length === 0) return;
		currentMatchIndex = (currentMatchIndex + 1) % searchMatches.length;
		const key = searchMatches[currentMatchIndex];
		if ($hierarchy) {
			selectedNode.set(findNodeByKey($hierarchy, key));
		}
	}

	/**
	 * Navigates to the previous search match.
	 */
	function previousMatch() {
		if (searchMatches.length === 0) return;
		currentMatchIndex = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length;
		const key = searchMatches[currentMatchIndex];
		if ($hierarchy) {
			selectedNode.set(findNodeByKey($hierarchy, key));
		}
	}

	/**
	 * Reactive block to scroll the selected element into view in the hierarchy tree.
	 */
	$: if ($selectedNode && rightTab === 'hierarchy') {
		tick().then(() => {
			const element = document.getElementById(`hierarchy-node-${$selectedNode.key}`);
			if (element) {
				element.scrollIntoView({
					behavior: 'smooth',
					block: 'center', // Center the element in the view
					inline: 'center'
				});
			}
		});
	}

	/**
	 * Reactive block to auto-refresh the hierarchy when the tab is switched to.
	 */
	$: if (rightTab === 'hierarchy' && $selectedSerial) {
		refreshHierarchy();
	}

	/**
	 * Derived store to generate a suggested XPath selector for the selected node.
	 */
	const generatedXPath = derived(selectedNode, ($node) => {
		if (!$node?.properties) return 'Select an element to see its XPath';
		const p = $node.properties;
		if (p['resource-id']) return `//*[@resource-id='${p['resource-id']}']`;
		if (p['content-desc']) return `//*[@content-desc='${p['content-desc']}']`;
		if (p['text']) return `//*[contains(@text, "${p['text']}")]`;
		return `//${$node.name}`;
	});

	// ─── Legacy Integration ──────────────────────────────────────────────────────────────────────
	let getAppVariables = () => ({});
	let callBackend: any = () => Promise.resolve();
	let legacyUpdateMessage: any = updateMessage; // Use our new notification system
	let PythonConsoleManager = { init: () => {}, refresh: () => {} };
	let escapeHtml = (s: string) => s;
	let openGlobalTab = (_evt: any, _name: string) => {};

	onMount(() => {
		if ((window as any).getAppVariablesForLlm)
			getAppVariables = (window as any).getAppVariablesForLlm;
		if ((window as any).callBackend) callBackend = (window as any).callBackend;
		// Use our new notification system for legacy compatibility
		legacyUpdateMessage = updateMessage;
		if ((window as any).PythonConsoleManager)
			PythonConsoleManager = (window as any).PythonConsoleManager;
		if ((window as any).escapeHtml) escapeHtml = (window as any).escapeHtml;
		if ((window as any).openGlobalTab) openGlobalTab = (window as any).openGlobalTab;

		// Make notification system globally available for legacy code
		(window as any).updateMessage = updateMessage;
		(window as any).updateGlobalMessage = updateMessage;
		(window as any).notificationStore = notificationStore;

		// Initialize panel states if they don't exist
		if (!panelActions.getPanel('left-panel')) {
			panelActions.updateDimensions('left-panel', { width: 350, minWidth: 300, maxWidth: 500 });
		}
		if (!panelActions.getPanel('middle-panel')) {
			panelActions.updateDimensions('middle-panel', { width: 400, minWidth: 300 });
		}
		if (!panelActions.getPanel('hierarchy-panel')) {
			panelActions.updateDimensions('hierarchy-panel', { width: 350, minWidth: 250, maxWidth: 600 });
		}
	});
</script>

<style>
	:global(body) {
		margin: 0;
		background: #111;
		color: #fff;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu,
			Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
	}

	main {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.layout {
		display: flex;
		flex: 1;
		gap: 0.5rem;
		padding: 0.5rem;
		min-height: 0;
		overflow: hidden;
	}

	/* Allow horizontal scrolling when hierarchy tab is active */
	.layout.hierarchy-active {
		overflow: visible;
	}

	.panel {
		background: #1e1e1e;
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid #333;
	}

	.panel-title {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		font-weight: bold;
		border-bottom: 1px solid #333;
		flex-shrink: 0;
	}

	.panel-content {
		flex: 1 1 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}

	.left-panel {
		flex: 1 1 0;
		min-width: var(--left-panel-min-width, 280px);
		max-width: var(--left-panel-max-width, 400px);
		transition: flex-basis 0.2s ease;
	}

	.screenshot-wrapper {
		flex: 1 1 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #000;
		padding: 0.5rem;
		min-height: 0;
		overflow: hidden;
	}

	.middle-panel {
		flex: 1 1 0;
		min-width: var(--middle-panel-min-width, 280px);
		max-width: var(--middle-panel-max-width, none);
		transition: flex-basis 0.2s ease;
	}

	.right-panel {
		flex: 1 1 0;
		min-width: var(--right-panel-min-width, 240px);
		max-width: var(--right-panel-max-width, none);
		transition: min-width 0.2s ease;
	}

	.tabs {
		display: flex;
		background: #252526;
		border-bottom: 1px solid #333;
		flex-shrink: 0;
	}

	.tab-button {
		padding: 0.6rem 1rem;
		cursor: pointer;
		background: transparent;
		border: none;
		color: #888;
		border-bottom: 2px solid transparent;
		font-size: 0.9rem;
		transition: color 0.2s ease;
	}

	.tab-button:hover {
		color: #ccc;
	}

	.tab-button.active {
		color: #fff;
		border-bottom-color: #007acc;
	}

	.tab-content {
		flex: 1;
		overflow: auto;
		padding: 0; /* Changed from 1rem to 0 to allow components to control their own padding */
		display: flex;
		flex-direction: column;
	}

	.right-panel .panel-content {
		padding: 0;
	}

	/* Allow horizontal scrolling for hierarchy tab specifically */
	.right-panel.hierarchy-active {
		min-width: 0;
	}

	.right-panel.hierarchy-active .panel-content {
		overflow: visible;
	}

	.hierarchy-controls {
		padding: 0.5rem;
		flex-shrink: 0;
		background: #1e1e1e;
		border-bottom: 1px solid #333;
		position: relative;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.search-input {
		flex-grow: 1;
		box-sizing: border-box;
		padding: 0.4rem 0.6rem;
		border-radius: 4px;
		border: 1px solid #3c3c3c;
		background: #2a2a2a;
		color: #fff;
		font-size: 13px;
	}
	.search-input:focus {
		outline: 1px solid #007acc;
	}

	.search-nav {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 12px;
		color: #aaa;
	}

	.search-nav button {
		background: #3c3c3c;
		border: 1px solid #555;
		color: #ddd;
		border-radius: 4px;
		cursor: pointer;
		font-weight: bold;
		padding: 2px 8px;
		line-height: 1.5;
	}
	.search-nav button:hover {
		background: #4f4f4f;
	}

	.tree-wrapper {
		flex-grow: 1;
		overflow-x: auto; /* Only horizontal scrolling */
		overflow-y: auto; /* Vertical scrolling */
		scrollbar-width: thin;
		scrollbar-color: #555 #2a2a2a;
		min-width: 0; /* Allow shrinking below content width */
		width: 100%; /* Take full container width */
		padding-left: 0.5rem; /* Move padding here from inline style */
	}

	.tree-wrapper ul {
		min-width: max-content; /* Ensure content determines width */
		width: fit-content; /* Allow tree to extend beyond container */
		padding-left: 0; /* Remove default ul padding */
	}

	.multi-select-controls {
		padding: 0.5rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
		border-top: 1px solid #333;
		background: #1a1a1a;
		flex-shrink: 0;
	}

	/* Responsive Design - Tablet and smaller screens */
	@media (max-width: 1200px) {
		.left-panel {
			min-width: 240px;
			max-width: 320px;
		}

		.middle-panel {
			min-width: 240px;
		}

		.right-panel {
			min-width: 200px;
		}

		.layout {
			gap: 0.25rem;
		}
	}

	@media (max-width: 900px) {
		.left-panel {
			min-width: 200px;
			max-width: 280px;
		}

		.middle-panel {
			min-width: 200px;
		}

		.right-panel {
			min-width: 180px;
		}

		.panel-title {
			padding: 0.4rem 0.75rem;
			font-size: 0.85rem;
		}

		.layout {
			gap: 0.25rem;
			padding: 0.25rem;
		}
	}

	@media (max-width: 768px) {
		.layout {
			flex-direction: column;
			gap: 0.5rem;
		}

		.left-panel,
		.middle-panel,
		.right-panel {
			flex: none;
			min-width: 100%;
			max-width: 100%;
		}

		.left-panel {
			order: 1;
			min-height: 300px;
		}

		.middle-panel {
			order: 2;
			min-height: 400px;
		}

		.right-panel {
			order: 3;
			min-height: 300px;
		}
	}
</style>

<main>
	<div
		class="layout"
		class:hierarchy-active={rightTab === 'hierarchy'}
		style="
			--left-panel-width: {$leftPanel?.dimensions?.width ? $leftPanel.dimensions.width + 'px' : '30%'};
			--left-panel-min-width: {$leftPanel?.dimensions?.minWidth ? $leftPanel.dimensions.minWidth + 'px' : '300px'};
			--left-panel-max-width: {$leftPanel?.dimensions?.maxWidth ? $leftPanel.dimensions.maxWidth + 'px' : '500px'};
			--middle-panel-width: {$middlePanel?.dimensions?.width ? $middlePanel.dimensions.width + 'px' : '35%'};
			--middle-panel-min-width: {$middlePanel?.dimensions?.minWidth ? $middlePanel.dimensions.minWidth + 'px' : '300px'};
			--right-panel-min-width: {$hierarchyPanel?.dimensions?.minWidth ? $hierarchyPanel.dimensions.minWidth + 'px' : '250px'};
			--right-panel-max-width: {$hierarchyPanel?.dimensions?.maxWidth ? $hierarchyPanel.dimensions.maxWidth + 'px' : 'none'};
		"
	>
		<div class="panel left-panel">
			<div class="panel-title">
				<span>Device</span>
				<DeviceSelectorPanel />
			</div>
			<div class="panel-content">
				<div class="screenshot-wrapper">
					<DeviceScreenshot
						bind:this={deviceScreenshotComponent}
						bind:interactionMode={deviceInteractionMode}
						bind:isRefreshing={deviceIsRefreshing}
					/>
				</div>
				<div class="multi-select-controls">
					<DeviceControls
						handleRefresh={handleDeviceRefresh}
						bind:interactionMode={deviceInteractionMode}
						bind:isRefreshing={deviceIsRefreshing}
					/>
					<MultiSelectToggle />
					<SelectedElementsList />
				</div>
			</div>
		</div>

		<div class="panel middle-panel">
			<div class="tabs">
				<button
					class="tab-button"
					class:active={midTab === 'assistant'}
					on:click={() => (midTab = 'assistant')}
				>
					LLM Assistant
				</button>
				<button
					class="tab-button"
					class:active={midTab === 'details'}
					on:click={() => (midTab = 'details')}
				>
					Element Details
				</button>
			</div>
			<div class="panel-content">
				{#if midTab === 'assistant'}
					<LLMAssistant
						{getAppVariables}
						{callBackend}
						updateMessage={legacyUpdateMessage}
						{PythonConsoleManager}
						{escapeHtml}
						{openGlobalTab}
					/>
				{:else}
					<PropertiesPanel generatedXPath={$generatedXPath} selectedNode={$selectedNode} />
				{/if}
			</div>
		</div>

		<div class="panel right-panel" class:hierarchy-active={rightTab === 'hierarchy'}>
			<div class="tabs">
				<button
					class="tab-button"
					class:active={rightTab === 'python'}
					on:click={() => (rightTab = 'python')}
				>
					Python Console
				</button>
				<button
					class="tab-button"
					class:active={rightTab === 'hierarchy'}
					on:click={() => (rightTab = 'hierarchy')}
				>
					UI Hierarchy
				</button>
			</div>
			<div class="panel-content">
				{#if rightTab === 'python'}
					<!-- Enhanced Python Console with integrated resizable output panel -->
					<PythonConsoleWithOutput serial={$selectedSerial} />
				{:else}
					{#if $isLoadingHierarchy}
						<p style="padding: 1rem; color: #888;">Loading UI hierarchy…</p>
					{:else if $hierarchyError}
						<p style="color: #e53935; padding: 1rem;">Error: {$hierarchyError}</p>
					{:else if !$hierarchy}
						<p style="padding: 1rem; color: #888;">No hierarchy available. Select a device.</p>
					{:else}
						<div class="hierarchy-controls">
							<input
								type="text"
								class="search-input"
								placeholder="Search name, text, or resource-id…"
								bind:value={hierarchySearchTerm}
							/>
							{#if hierarchySearchTerm && searchMatches.length > 0}
								<div class="search-nav">
									<span>
										{currentMatchIndex + 1} of {searchMatches.length}
									</span>
									<button on:click={previousMatch} title="Previous Match">‹</button>
									<button on:click={nextMatch} title="Next Match">›</button>
								</div>
							{/if}
						</div>
						<div class="tree-wrapper">
							<ul>
								<HierarchyTree
									node={$hierarchy}
									bind:expanded={expandedKeys}
									searchTerm={hierarchySearchTerm}
									currentMatchKey={searchMatches[currentMatchIndex]}
								/>
							</ul>
						</div>
					{/if}
				{/if}
			</div>
		</div>
	</div>

	<!-- ✅ Floating Console Output: Rendered here, on top of everything else. -->
	{#if $pythonConsoleStore.isOpen}
		<ConsoleOutput />
	{/if}

	<!-- ✅ Global Notification System: Toast and global messages -->
	<NotificationContainer />
</main>

