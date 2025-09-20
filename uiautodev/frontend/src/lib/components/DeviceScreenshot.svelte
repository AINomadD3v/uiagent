<script lang="ts">
	import { tick, onMount, onDestroy, createEventDispatcher } from 'svelte';
	import { derived, get } from 'svelte/store';

	const dispatch = createEventDispatcher();

	// ✅ 1. Import all necessary stores and functions
	import { screenshotStore, refreshScreenshot, screenshotRefreshTrigger } from '$lib/stores/screenshot';
	import { hierarchy, refreshHierarchy } from '$lib/stores/hierarchy'; // This is the key to the fix
	import {
		selectedSerial,
		selectedNode,
		hoveredNode,
		multiSelectMode,
		multiSelectedNodes,
		type NodeInfo
	} from '$lib/stores/uiagent';

	// ✅ NEW: Import device interaction API
	import { tapDevice } from '$lib/api/deviceClient';

	// --- Local state & element bindings ---
	let imgEl: HTMLImageElement;
	let canvasEl: HTMLCanvasElement;
	let containerEl: HTMLDivElement;
	let isRefreshing = false;

	// Toggle between device interaction and element selection
	let interactionMode: 'navigate' | 'select' = 'select'; // Default to select mode to prevent accidental device interactions

	// Prevent rapid successive device interactions
	let lastDeviceInteraction = 0;

	let tooltip = {
		visible: false,
		x: 0,
		y: 0,
		content: ''
	};

	// ✅ 2. Use the imported trigger store for reactivity
	$: screenshotUrl = $selectedSerial
		? `/api/android/${$selectedSerial}/screenshot/0?t=${$screenshotRefreshTrigger}`
		: '';

	// ✅ 3. The new, combined refresh handler
	async function handleRefresh() {
		if (isRefreshing || !$selectedSerial) return;
		isRefreshing = true;
		console.log('Refreshing hierarchy and screenshot...');

		try {
			// First, tell the hierarchy to refresh. We `await` this to ensure
			// the new locator data is fetched before we proceed.
			await refreshHierarchy();

			// Then, call the exported function to refresh the screenshot.
			refreshScreenshot();
		} catch (error) {
			console.error('Failed to refresh:', error);
		}
		// The loading state will be turned off when the image finishes loading.
	}

	async function measureImage() {
		await tick();
		if (!imgEl) return;

		screenshotStore.update((current) => ({
			...current,
			renderedWidth: imgEl.width,
			renderedHeight: imgEl.height,
			naturalWidth: imgEl.naturalWidth,
			naturalHeight: imgEl.naturalHeight
		}));

		// Force canvas dimension sync after store update
		await tick();
		if (canvasEl && imgEl.naturalWidth > 0 && imgEl.naturalHeight > 0) {
			const renderedSize = getRenderedImageSize(imgEl);

			canvasEl.width = renderedSize.width;
			canvasEl.height = renderedSize.height;
			canvasEl.style.width = renderedSize.width + 'px';
			canvasEl.style.height = renderedSize.height + 'px';

			console.log('Canvas dimensions synchronized to rendered image size:', {
				canvasWidth: canvasEl.width,
				canvasHeight: canvasEl.height,
				renderedWidth: renderedSize.width,
				renderedHeight: renderedSize.height,
				naturalWidth: imgEl.naturalWidth,
				naturalHeight: imgEl.naturalHeight
			});
		}

		isRefreshing = false; // Stop the loading spinner
	}

	const scaledNodes = derived([hierarchy, screenshotStore], ([$hierarchy, $screenshot]) => {
		const allNodes: (NodeInfo & { pxRect: { x: number; y: number; w: number; h: number } })[] =
			[];
		if (!$hierarchy || $screenshot.renderedWidth === 0) {
			return allNodes;
		}

		function recurse(node: NodeInfo) {
			if (node.bounds?.length === 4) {
				const [x1, y1, x2, y2] = node.bounds;
				const scaledRect = {
					x: x1 * $screenshot.renderedWidth,
					y: y1 * $screenshot.renderedHeight,
					w: (x2 - x1) * $screenshot.renderedWidth,
					h: (y2 - y1) * $screenshot.renderedHeight
				};
				if (scaledRect.w > 0 && scaledRect.h > 0) {
					allNodes.push({ ...node, pxRect: scaledRect });
				}
			}
			node.children?.forEach(recurse);
		}
		recurse($hierarchy);
		return allNodes;
	});

	function findBestElement(candidates: NodeInfo[]): NodeInfo | null {
		if (candidates.length === 0) return null;
		if (candidates.length === 1) return candidates[0];

		return candidates.sort((a, b) => {
			// Prioritize clickable elements
			const aClickable = a.properties?.clickable === true || a.properties?.clickable === 'true';
			const bClickable = b.properties?.clickable === true || b.properties?.clickable === 'true';
			if (aClickable && !bClickable) return -1;
			if (!aClickable && bClickable) return 1;

			// Calculate areas
			const areaA = (a.bounds![2] - a.bounds![0]) * (a.bounds![3] - a.bounds![1]);
			const areaB = (b.bounds![2] - b.bounds![0]) * (b.bounds![3] - b.bounds![1]);

			// For same-sized elements, prefer more specific ones
			if (Math.abs(areaA - areaB) < 0.0001) {
				const aScore = (a.properties?.['resource-id'] ? 2 : 0) +
							   (a.properties?.text ? 1 : 0) +
							   (a.properties?.['content-desc'] ? 1 : 0) -
							   (a.name === 'android.widget.FrameLayout' ||
								a.name === 'android.view.ViewGroup' ? 1 : 0);
				const bScore = (b.properties?.['resource-id'] ? 2 : 0) +
							   (b.properties?.text ? 1 : 0) +
							   (b.properties?.['content-desc'] ? 1 : 0) -
							   (b.name === 'android.widget.FrameLayout' ||
								b.name === 'android.view.ViewGroup' ? 1 : 0);
				return bScore - aScore;
			}

			// Prefer smaller areas (more specific elements)
			return areaA - areaB;
		})[0];
	}

	function getNodeAt(evt: MouseEvent): NodeInfo | null {
		if (!$hierarchy || !canvasEl) {
			console.log('❌ getNodeAt: Missing hierarchy or canvas', {
				hasHierarchy: !!$hierarchy,
				hasCanvas: !!canvasEl
			});
			return null;
		}

		// Get Canvas coordinates directly - same as HTML version
		const canvasRect = canvasEl.getBoundingClientRect();
		const x = evt.clientX - canvasRect.left;
		const y = evt.clientY - canvasRect.top;

		console.log('🎯 getNodeAt coordinates:', {
			clientX: evt.clientX,
			clientY: evt.clientY,
			canvasRect: { left: canvasRect.left, top: canvasRect.top, width: canvasRect.width, height: canvasRect.height },
			canvasX: x,
			canvasY: y
		});

		if (x < 0 || y < 0 || x > canvasRect.width || y > canvasRect.height) {
			console.log('❌ getNodeAt: Click outside canvas bounds');
			return null;
		}

		// Convert to relative coordinates (0-1 range)
		const relX = x / canvasRect.width;
		const relY = y / canvasRect.height;
		const candidates: NodeInfo[] = [];


		// Only log in selection mode to reduce noise
		if (interactionMode === 'select') {
			console.log('🔍 Selection mode - searching for element at:', { relX, relY });
		}

		// Deep recursive search
		let nodeCount = 0;
		function findAllElementsRecursive(node: NodeInfo) {
			nodeCount++;

			if (node.bounds?.length === 4) {
				const [x1, y1, x2, y2] = node.bounds;
				const nodeWidth = x2 - x1;
				const nodeHeight = y2 - y1;

				if (nodeWidth > 0 && nodeHeight > 0 &&
					node.properties?.visibility !== 'gone') {
					const isXWithin = relX >= x1 && relX <= x2;
					const isYWithin = relY >= y1 && relY <= y2;

					if (isXWithin && isYWithin) {
						candidates.push(node);
					}
				}
			}

			// Recurse into children
			if (node.children?.length > 0) {
				for (const child of node.children) {
					if (child && typeof child === 'object') {
						findAllElementsRecursive(child);
					}
				}
			}
		}

		findAllElementsRecursive($hierarchy);

		const result = findBestElement(candidates);

		// Only log results in selection mode
		if (interactionMode === 'select') {
			console.log('🔍 Found:', result ? `${result.name} (${result.properties?.text || 'no text'})` : 'No element');
		}

		return result;
	}

	function onMouseMove(evt: MouseEvent) {
		const node = getNodeAt(evt);
		hoveredNode.set(node);
		if (node) {
			let content = `<b>${node.name}</b>`;
			const text = node.properties?.text;
			const desc = node.properties?.['content-desc'];
			const resId = node.properties?.['resource-id'];
			if (resId) content += `<br><small>ID:</small> ${resId}`;
			if (text) content += `<br><small>Text:</small> ${text}`;
			if (desc) content += `<br><small>Desc:</small> ${desc}`;
			tooltip = { visible: true, x: evt.clientX + 15, y: evt.clientY + 15, content };
		} else {
			tooltip.visible = false;
		}
	}

	function onMouseLeave() {
		hoveredNode.set(null);
		tooltip.visible = false;
	}

	// Canvas drawing function - matches HTML version approach
	function drawCanvasOverlay() {
		if (!canvasEl || !$screenshotStore.renderedWidth || !$screenshotStore.renderedHeight) return;

		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;

		// Clear canvas
		ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

		// Draw rectangles for each scaled node
		for (const node of $scaledNodes) {
			const isSelected = $selectedNode?.key === node.key;
			const isHovered = $hoveredNode?.key === node.key && !isSelected;
			const isMultiSelected = $multiSelectMode && $multiSelectedNodes.some((n) => n.key === node.key);

			if (isSelected || isHovered || isMultiSelected) {
				ctx.strokeStyle = isSelected
					? 'rgba(0, 120, 255, 0.95)'
					: isHovered
					? 'rgba(0, 255, 120, 0.9)'
					: 'rgba(255, 165, 0, 0.9)';

				ctx.lineWidth = 2;
				ctx.fillStyle = isSelected
					? 'rgba(0, 120, 255, 0.25)'
					: isMultiSelected
					? 'rgba(255, 165, 0, 0.2)'
					: 'transparent';

				ctx.strokeRect(node.pxRect.x, node.pxRect.y, node.pxRect.w, node.pxRect.h);
				if (ctx.fillStyle !== 'transparent') {
					ctx.fillRect(node.pxRect.x, node.pxRect.y, node.pxRect.w, node.pxRect.h);
				}
			}
		}
	}

	// Reactive statements to redraw canvas when state changes
	$: if (canvasEl && $scaledNodes) {
		drawCanvasOverlay();
	}
	$: if (canvasEl && $selectedNode) {
		drawCanvasOverlay();
	}
	$: if (canvasEl && $hoveredNode) {
		drawCanvasOverlay();
	}
	$: if (canvasEl && $multiSelectedNodes) {
		drawCanvasOverlay();
	}

	async function onClick(evt: MouseEvent) {
		console.log('Canvas click detected:', {
			canvasWidth: canvasEl?.width,
			canvasHeight: canvasEl?.height,
			storeWidth: $screenshotStore.renderedWidth,
			storeHeight: $screenshotStore.renderedHeight,
			rectWidth: canvasEl?.getBoundingClientRect().width,
			rectHeight: canvasEl?.getBoundingClientRect().height
		});

		const clickedNode = getNodeAt(evt);

		// Enable multi-select mode if Ctrl/Cmd is held, but don't disable it
		// This allows both manual toggle button and keyboard shortcuts to work
		if (evt.ctrlKey || evt.metaKey) {
			multiSelectMode.set(true);
		}

		if (!clickedNode) {
			if (!$multiSelectMode) {
				selectedNode.set(null);
				multiSelectedNodes.set([]);
			}
			return;
		}

		// Update UI state (existing logic)
		if ($multiSelectMode) {
			const list = get(multiSelectedNodes);
			const idx = list.findIndex((n) => n.key === clickedNode.key);
			if (idx >= 0) {
				list.splice(idx, 1);
			} else {
				list.push(clickedNode);
			}
			multiSelectedNodes.set(list);
			selectedNode.set(list.at(-1) || null);
		} else {
			multiSelectedNodes.set([]);
			selectedNode.set(clickedNode);
		}

		// Device interaction only in navigate mode with debouncing
		if (interactionMode === 'navigate' && clickedNode && clickedNode.bounds && $selectedSerial) {
			const now = Date.now();
			if (now - lastDeviceInteraction < 1000) {
				console.log('🚫 Device interaction throttled - too soon after last interaction');
				return;
			}
			lastDeviceInteraction = now;

			try {
				// Calculate center point of the element
				const [x1, y1, x2, y2] = clickedNode.bounds;
				const centerX = (x1 + x2) / 2;
				const centerY = (y1 + y2) / 2;

				console.log('🎯 Sending device tap:', { centerX, centerY, element: clickedNode.name });

				// Send tap command to device using percentage coordinates
				await tapDevice($selectedSerial, centerX, centerY, true);

				// Longer delay and prevent cascading refreshes
				setTimeout(async () => {
					if (!isRefreshing) {
						console.log('🔄 Refreshing after device interaction');
						await refreshHierarchy();
						refreshScreenshot();
					}
				}, 500); // Longer delay to prevent rapid refreshes

			} catch (error) {
				console.error('Device tap failed:', error);
				// Reset throttle on error
				lastDeviceInteraction = 0;
			}
		} else if (interactionMode === 'select') {
			console.log('🔍 Selection mode - no device interaction');
		}
	}

	// Direct event listener as fallback for Svelte binding issues
	let canvasClickHandler: ((evt: MouseEvent) => void) | null = null;

	onMount(() => {
		console.log('DeviceScreenshot component mounted');
		// Ensure direct event listeners are attached
		if (canvasEl) {
			setupDirectEventListeners();
		}
	});

	onDestroy(() => {
		if (canvasEl && canvasClickHandler) {
			canvasEl.removeEventListener('click', canvasClickHandler);
			console.log('Direct canvas event listener removed');
		}
	});

	function setupDirectEventListeners() {
		if (!canvasEl || canvasClickHandler) return;

		canvasClickHandler = (evt: MouseEvent) => {
			onClick(evt);
		};

		canvasEl.addEventListener('click', canvasClickHandler);
		console.log('🔗 Direct canvas event listener attached to:', canvasEl);

		// Also add debugging listener to parent container
		if (containerEl) {
			const containerHandler = (evt: MouseEvent) => {
				console.log('📦 Container click detected:', {
					target: evt.target,
					currentTarget: evt.currentTarget,
					clientX: evt.clientX,
					clientY: evt.clientY,
					isCanvas: evt.target === canvasEl
				});
			};
			containerEl.addEventListener('click', containerHandler);
			console.log('🔗 Container debug listener attached to:', containerEl);
		}
	}

	// Reactive setup for direct event listeners
	$: if (canvasEl && $screenshotStore.renderedWidth > 0) {
		setupDirectEventListeners();

		// COMPREHENSIVE CANVAS DEBUG
		const canvasRect = canvasEl.getBoundingClientRect();
		const computedStyle = window.getComputedStyle(canvasEl);
		const parent = canvasEl.parentElement;
		const parentRect = parent?.getBoundingClientRect();

		console.log('🔍 COMPREHENSIVE CANVAS DEBUG:', {
			// Element existence
			hasCanvasElement: !!canvasEl,
			hasParent: !!parent,

			// Canvas dimensions
			canvasWidth: canvasEl.width,
			canvasHeight: canvasEl.height,
			canvasStyleWidth: canvasEl.style.width,
			canvasStyleHeight: canvasEl.style.height,

			// Bounding rect (actual screen position)
			canvasRect: {
				x: canvasRect.x,
				y: canvasRect.y,
				width: canvasRect.width,
				height: canvasRect.height,
				top: canvasRect.top,
				left: canvasRect.left
			},

			// Parent positioning
			parentRect: parentRect ? {
				x: parentRect.x,
				y: parentRect.y,
				width: parentRect.width,
				height: parentRect.height
			} : null,

			// CSS properties that might affect events
			cssProps: {
				position: computedStyle.position,
				pointerEvents: computedStyle.pointerEvents,
				zIndex: computedStyle.zIndex,
				display: computedStyle.display,
				visibility: computedStyle.visibility,
				opacity: computedStyle.opacity,
				transform: computedStyle.transform
			},

			// Event listener status
			hasDirectListener: !!canvasClickHandler,

			// Store state
			storeWidth: $screenshotStore.renderedWidth,
			storeHeight: $screenshotStore.renderedHeight
		});

		// Fix common issues
		if (computedStyle.pointerEvents === 'none') {
			console.warn('🔧 Fixing pointer-events: none');
			canvasEl.style.pointerEvents = 'all';
		}

		if (canvasRect.width === 0 || canvasRect.height === 0) {
			console.error('❌ Canvas has zero dimensions in DOM!');
		}

		// Canvas is ready for interaction
	}

	function onKeyDown(evt: KeyboardEvent) {
		if (evt.key === 'r' && (evt.metaKey || evt.ctrlKey)) {
			evt.preventDefault();
			handleRefresh();
		}
		if (evt.key === 'Enter' || evt.key === ' ') {
			const hovered = get(hoveredNode);
			if (hovered && hovered.bounds) {
				const mockEvent = {
					ctrlKey: evt.ctrlKey,
					metaKey: evt.metaKey
				} as MouseEvent;
				onClick(mockEvent);
			}
		}
	}

	// Calculate actual rendered image dimensions when using object-fit: contain
	function getRenderedImageSize(img: HTMLImageElement): { width: number; height: number } {
		const imgRect = img.getBoundingClientRect();
		const containerWidth = imgRect.width;
		const containerHeight = imgRect.height;

		const naturalWidth = img.naturalWidth;
		const naturalHeight = img.naturalHeight;

		if (naturalWidth === 0 || naturalHeight === 0) {
			return { width: 0, height: 0 };
		}

		const containerAspect = containerWidth / containerHeight;
		const imageAspect = naturalWidth / naturalHeight;

		let renderedWidth, renderedHeight;

		if (imageAspect > containerAspect) {
			// Image is wider - limited by container width
			renderedWidth = containerWidth;
			renderedHeight = containerWidth / imageAspect;
		} else {
			// Image is taller - limited by container height
			renderedHeight = containerHeight;
			renderedWidth = containerHeight * imageAspect;
		}

		return { width: renderedWidth, height: renderedHeight };
	}

	// Export functions and variables for use by parent components
	export { handleRefresh, interactionMode, isRefreshing };
</script>

<style>
	.container {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		cursor: crosshair;
	}
    /* ✅ NEW: This wrapper will contain the image and overlay, ensuring they are aligned. */
	.image-wrapper {
		position: relative;
        /* This prevents extra space from being added below the image element */
		line-height: 0;
		/* Ensure wrapper takes full container size for proper image scaling */
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	img {
		display: block;
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
	}
	.overlay {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		/* Ensure canvas maintains aspect ratio and doesn't get CSS overrides */
		width: auto !important;
		height: auto !important;
		object-fit: contain;
		pointer-events: all !important; /* Force enable pointer events on canvas */
		cursor: crosshair; /* Show interactive cursor */
		z-index: 2; /* Ensure canvas is above image */
	}
	.placeholder {
		color: #666;
		text-align: center;
	}
	.tooltip {
		position: fixed;
		background-color: rgba(30, 30, 30, 0.95);
		color: #f0f0f0;
		border: 1px solid #666;
		border-radius: 6px;
		padding: 10px 14px;
		font-size: 13px;
		font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
		pointer-events: none;
		z-index: 1000;
		max-width: 450px;
		line-height: 1.6;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
		word-break: break-all;
	}
	:global(.tooltip b) {
		color: #92c9ff;
		font-weight: bold;
	}
	:global(.tooltip small) {
		color: #999;
	}
</style>

<div
	bind:this={containerEl}
	class="container"
	role="application"
	tabindex="0"
	aria-label="Interactive Device Screenshot"
	on:keydown={onKeyDown}
>
	{#if !$selectedSerial}
		<div class="placeholder">No device selected</div>
	{:else}
        <!-- ✅ NEW WRAPPER DIV -->
		<div class="image-wrapper">

			<img
				bind:this={imgEl}
				src={screenshotUrl}
				alt="Device screenshot"
				on:load={measureImage}
				on:error={() => {
					console.error('Failed to load screenshot for', screenshotUrl);
					isRefreshing = false;
				}}
			/>

			<!-- Canvas overlay - same approach as working HTML version -->
			<!-- Canvas overlay - using direct event listener instead of on:click -->
			<canvas
				bind:this={canvasEl}
				class="overlay"
				width={$screenshotStore.renderedWidth}
				height={$screenshotStore.renderedHeight}
				on:click={onClick}
				on:mousemove={onMouseMove}
				on:mouseleave={onMouseLeave}
			></canvas>
		</div>
	{/if}

	{#if tooltip.visible}
		<div class="tooltip" style="left: {tooltip.x}px; top: {tooltip.y}px;" role="tooltip">
			{@html tooltip.content}
		</div>
	{/if}
</div>


