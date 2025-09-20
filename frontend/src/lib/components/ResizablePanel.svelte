<!-- Resizable Panel Component
     Provides drag-based resizing functionality with state persistence -->

<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import { panelActions, constrainDimension, type PanelDimensions } from '$lib/stores/panelState';

	// ─── Props ───────────────────────────────────────────────────────────────

	export let panelId: string;
	export let direction: 'vertical' | 'horizontal' | 'both' = 'vertical';
	export let isOpen: boolean = true;
	export let dimensions: PanelDimensions = {};
	export let showDragHandle: boolean = true;
	export let dragHandlePosition: 'top' | 'bottom' | 'left' | 'right' | 'corner' = 'top';
	export let className: string = '';

	// ─── State ──────────────────────────────────────────────────────────────

	let isDragging = false;
	let dragStart = { x: 0, y: 0 };
	let initialDimensions = { width: 0, height: 0 };
	let panelElement: HTMLDivElement;

	const dispatch = createEventDispatcher<{
		resize: { width?: number; height?: number };
		resizeStart: void;
		resizeEnd: void;
	}>();

	// ─── Computed Values ────────────────────────────────────────────────────

	$: currentWidth = dimensions.width || 300;
	$: currentHeight = dimensions.height || 200;
	$: minWidth = dimensions.minWidth || 100;
	$: minHeight = dimensions.minHeight || 50;
	$: maxWidth = dimensions.maxWidth;
	$: maxHeight = dimensions.maxHeight;

	$: canResizeHorizontal = direction === 'horizontal' || direction === 'both';
	$: canResizeVertical = direction === 'vertical' || direction === 'both';

	// ─── Event Handlers ─────────────────────────────────────────────────────

	function handleDragStart(event: MouseEvent) {
		if (!isOpen || typeof document === 'undefined') return;

		event.preventDefault();
		event.stopPropagation();

		isDragging = true;
		dragStart = { x: event.clientX, y: event.clientY };
		initialDimensions = {
			width: panelElement.offsetWidth,
			height: panelElement.offsetHeight
		};

		// Set appropriate cursor and prevent text selection
		const cursor = getCursorForDirection();
		document.body.style.cursor = cursor;
		document.body.style.userSelect = 'none';

		dispatch('resizeStart');

		// Add global event listeners
		document.addEventListener('mousemove', handleDragMove);
		document.addEventListener('mouseup', handleDragEnd);
	}

	function handleDragMove(event: MouseEvent) {
		if (!isDragging || !isOpen) return;

		event.preventDefault();

		const deltaX = event.clientX - dragStart.x;
		const deltaY = event.clientY - dragStart.y;

		let newWidth = initialDimensions.width;
		let newHeight = initialDimensions.height;

		// Calculate new dimensions based on drag direction and handle position
		if (canResizeHorizontal) {
			if (dragHandlePosition === 'right' || dragHandlePosition === 'corner') {
				newWidth = initialDimensions.width + deltaX;
			} else if (dragHandlePosition === 'left') {
				newWidth = initialDimensions.width - deltaX;
			}
		}

		if (canResizeVertical) {
			if (dragHandlePosition === 'bottom' || dragHandlePosition === 'corner') {
				newHeight = initialDimensions.height + deltaY;
			} else if (dragHandlePosition === 'top') {
				newHeight = initialDimensions.height - deltaY;
			}
		}

		// Apply constraints
		newWidth = constrainDimension(newWidth, minWidth, maxWidth);
		newHeight = constrainDimension(newHeight, minHeight, maxHeight);

		// Update dimensions
		const updatedDimensions: Partial<PanelDimensions> = {};
		if (canResizeHorizontal) updatedDimensions.width = newWidth;
		if (canResizeVertical) updatedDimensions.height = newHeight;

		panelActions.updateDimensions(panelId, updatedDimensions);

		dispatch('resize', { width: newWidth, height: newHeight });
	}

	function handleDragEnd() {
		if (!isDragging || typeof document === 'undefined') return;

		isDragging = false;

		// Reset cursor and text selection
		document.body.style.cursor = '';
		document.body.style.userSelect = '';

		dispatch('resizeEnd');

		// Remove global event listeners
		document.removeEventListener('mousemove', handleDragMove);
		document.removeEventListener('mouseup', handleDragEnd);
	}

	function getCursorForDirection(): string {
		if (direction === 'both' || dragHandlePosition === 'corner') {
			return 'nwse-resize';
		} else if (canResizeHorizontal) {
			return 'ew-resize';
		} else if (canResizeVertical) {
			return 'ns-resize';
		}
		return 'default';
	}

	// ─── Lifecycle ──────────────────────────────────────────────────────────

	onMount(() => {
		// Ensure cleanup on component destruction
		return () => {
			if (typeof document !== 'undefined') {
				document.removeEventListener('mousemove', handleDragMove);
				document.removeEventListener('mouseup', handleDragEnd);
			}
		};
	});

	onDestroy(() => {
		// Reset any global styles (browser only)
		if (typeof document !== 'undefined') {
			document.body.style.cursor = '';
			document.body.style.userSelect = '';
		}
	});
</script>

<div
	bind:this={panelElement}
	class="resizable-panel {className}"
	class:is-open={isOpen}
	class:is-dragging={isDragging}
	style="width: {canResizeHorizontal ? currentWidth + 'px' : 'auto'}; height: {canResizeVertical ? currentHeight + 'px' : 'auto'};"
>
	<!-- Panel Content -->
	<div class="panel-content">
		<slot />
	</div>

	<!-- Drag Handle -->
	{#if showDragHandle && isOpen}
		<div
			class="drag-handle drag-handle--{dragHandlePosition}"
			class:draggable-horizontal={canResizeHorizontal}
			class:draggable-vertical={canResizeVertical}
			class:draggable-both={direction === 'both'}
			on:mousedown={handleDragStart}
			role="separator"
			aria-label="Resize panel"
			title="Drag to resize"
		>
			{#if direction === 'both' || dragHandlePosition === 'corner'}
				<div class="drag-handle-icon drag-handle-icon--corner"></div>
			{:else if canResizeVertical}
				<div class="drag-handle-icon drag-handle-icon--horizontal"></div>
			{:else if canResizeHorizontal}
				<div class="drag-handle-icon drag-handle-icon--vertical"></div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.resizable-panel {
		position: relative;
		display: flex;
		flex-direction: column;
		background: var(--panel-background, #1e1e1e);
		border: 1px solid var(--panel-border, #333);
		transition: opacity 0.2s ease;
	}

	.resizable-panel:not(.is-open) {
		opacity: 0.5;
		pointer-events: none;
	}

	.panel-content {
		flex: 1;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
	}

	/* ─── Drag Handle Styles ─────────────────────────────────────────────── */

	.drag-handle {
		position: absolute;
		z-index: 10;
		background: var(--drag-handle-background, rgba(255, 255, 255, 0.1));
		transition: background-color 0.2s ease, opacity 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0.6;
	}

	.drag-handle:hover {
		background: var(--drag-handle-hover-background, rgba(255, 255, 255, 0.2));
		opacity: 1;
	}

	.is-dragging .drag-handle {
		background: var(--drag-handle-active-background, rgba(0, 122, 204, 0.3));
		opacity: 1;
	}

	/* Handle Positioning */
	.drag-handle--top {
		top: 0;
		left: 0;
		right: 0;
		height: 6px;
		cursor: ns-resize;
		border-bottom: 1px solid var(--drag-handle-border, #444);
	}

	.drag-handle--bottom {
		bottom: 0;
		left: 0;
		right: 0;
		height: 6px;
		cursor: ns-resize;
		border-top: 1px solid var(--drag-handle-border, #444);
	}

	.drag-handle--left {
		top: 0;
		bottom: 0;
		left: 0;
		width: 6px;
		cursor: ew-resize;
		border-right: 1px solid var(--drag-handle-border, #444);
	}

	.drag-handle--right {
		top: 0;
		bottom: 0;
		right: 0;
		width: 6px;
		cursor: ew-resize;
		border-left: 1px solid var(--drag-handle-border, #444);
	}

	.drag-handle--corner {
		bottom: 0;
		right: 0;
		width: 16px;
		height: 16px;
		cursor: nwse-resize;
		border-top: 1px solid var(--drag-handle-border, #444);
		border-left: 1px solid var(--drag-handle-border, #444);
	}

	/* ─── Drag Handle Icons ──────────────────────────────────────────────── */

	.drag-handle-icon {
		pointer-events: none;
		opacity: 0.7;
	}

	.drag-handle-icon--horizontal {
		width: 20px;
		height: 2px;
		background: repeating-linear-gradient(
			to right,
			transparent,
			transparent 2px,
			var(--drag-handle-icon-color, #888) 2px,
			var(--drag-handle-icon-color, #888) 4px
		);
	}

	.drag-handle-icon--vertical {
		width: 2px;
		height: 20px;
		background: repeating-linear-gradient(
			to bottom,
			transparent,
			transparent 2px,
			var(--drag-handle-icon-color, #888) 2px,
			var(--drag-handle-icon-color, #888) 4px
		);
	}

	.drag-handle-icon--corner {
		width: 12px;
		height: 12px;
		background: repeating-linear-gradient(
			-45deg,
			transparent,
			transparent 2px,
			var(--drag-handle-icon-color, #888) 2px,
			var(--drag-handle-icon-color, #888) 3px
		);
	}

	/* ─── Global Dragging State ──────────────────────────────────────────── */

	:global(body.dragging-resize) {
		user-select: none !important;
		cursor: inherit !important;
	}

	:global(body.dragging-resize *) {
		pointer-events: none !important;
	}

	/* ─── Responsive Adjustments ─────────────────────────────────────────── */

	@media (max-width: 768px) {
		.drag-handle {
			opacity: 1; /* More visible on touch devices */
		}

		.drag-handle--top,
		.drag-handle--bottom {
			height: 8px; /* Larger touch target */
		}

		.drag-handle--left,
		.drag-handle--right {
			width: 8px; /* Larger touch target */
		}

		.drag-handle--corner {
			width: 20px;
			height: 20px;
		}
	}

	/* ─── Dark Mode Adjustments ──────────────────────────────────────────── */

	@media (prefers-color-scheme: dark) {
		.resizable-panel {
			--panel-background: #1e1e1e;
			--panel-border: #333;
			--drag-handle-background: rgba(255, 255, 255, 0.1);
			--drag-handle-hover-background: rgba(255, 255, 255, 0.2);
			--drag-handle-active-background: rgba(0, 122, 204, 0.3);
			--drag-handle-border: #444;
			--drag-handle-icon-color: #888;
		}
	}

	/* ─── High Contrast Mode ─────────────────────────────────────────────── */

	@media (prefers-contrast: high) {
		.drag-handle {
			border-width: 2px;
			opacity: 1;
		}

		.drag-handle-icon {
			opacity: 1;
		}
	}

	/* ─── Reduced Motion ─────────────────────────────────────────────────── */

	@media (prefers-reduced-motion: reduce) {
		.resizable-panel,
		.drag-handle {
			transition: none;
		}
	}
</style>