<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import type { ToastNotification } from '$lib/stores/notifications';

	// ─── PROPS ───────────────────────────────────────────────────────────────────────────────────

	/** The toast notification data to display */
	export let toast: ToastNotification;

	// ─── EVENT DISPATCHER ───────────────────────────────────────────────────────────────────────

	const dispatch = createEventDispatcher<{
		dismiss: { id: string };
		close: { id: string };
	}>();

	// ─── COMPONENT STATE ─────────────────────────────────────────────────────────────────────────

	let toastElement: HTMLDivElement;
	let progressBar: HTMLDivElement;
	let animationId: number;

	// ─── LIFECYCLE ───────────────────────────────────────────────────────────────────────────────

	onMount(() => {
		// Start progress bar animation if toast has duration
		if (toast.duration > 0) {
			startProgressAnimation();
		}

		return () => {
			if (animationId) {
				cancelAnimationFrame(animationId);
			}
		};
	});

	// ─── METHODS ─────────────────────────────────────────────────────────────────────────────────

	/**
	 * Handles manual dismissal of the toast
	 */
	function handleDismiss() {
		dispatch('dismiss', { id: toast.id });
	}

	/**
	 * Handles clicking on the toast body (optional: could auto-dismiss)
	 */
	function handleToastClick() {
		// For now, do nothing. Could auto-dismiss or show more details
	}

	/**
	 * Handles keyboard interaction for accessibility
	 */
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			handleDismiss();
		}
	}

	/**
	 * Starts the progress bar animation for timed toasts
	 */
	function startProgressAnimation() {
		if (!progressBar || toast.duration <= 0) return;

		const startTime = Date.now();
		const duration = toast.duration;

		function animate() {
			const elapsed = Date.now() - startTime;
			const progress = Math.min(elapsed / duration, 1);

			if (progressBar) {
				progressBar.style.width = `${(1 - progress) * 100}%`;
			}

			if (progress < 1) {
				animationId = requestAnimationFrame(animate);
			}
		}

		animationId = requestAnimationFrame(animate);
	}

	/**
	 * Gets the appropriate icon for the notification type
	 */
	function getTypeIcon(type: string): string {
		switch (type) {
			case 'success': return '✓';
			case 'error': return '✕';
			case 'warning': return '⚠';
			case 'info':
			default: return 'ℹ';
		}
	}

	/**
	 * Gets the ARIA role for the notification type
	 */
	function getAriaRole(type: string): string {
		switch (type) {
			case 'error': return 'alert';
			case 'warning': return 'alert';
			default: return 'status';
		}
	}
</script>

<div
	bind:this={toastElement}
	class="toast-notification toast-{toast.type}"
	class:visible={toast.visible}
	role={getAriaRole(toast.type)}
	aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
	aria-atomic="true"
	tabindex="-1"
	on:click={handleToastClick}
	on:keydown={handleKeydown}
>
	<!-- Toast Content -->
	<div class="toast-content">
		<div class="toast-icon" aria-hidden="true">
			{getTypeIcon(toast.type)}
		</div>
		<div class="toast-message">
			{toast.message}
		</div>
		<button
			class="toast-close"
			type="button"
			aria-label="Close notification"
			title="Close (Esc)"
			on:click|stopPropagation={handleDismiss}
		>
			×
		</button>
	</div>

	<!-- Progress Bar for Timed Toasts -->
	{#if toast.duration > 0}
		<div class="toast-progress-container">
			<div bind:this={progressBar} class="toast-progress-bar"></div>
		</div>
	{/if}
</div>

<style>
	.toast-notification {
		position: relative;
		min-width: 280px;
		max-width: 400px;
		background: #252526;
		border: 1px solid #4a4a4a;
		border-radius: 6px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
		color: #d4d4d4;
		font-size: 14px;
		opacity: 0;
		transform: translateX(100%);
		transition: opacity 0.3s ease, transform 0.3s ease;
		overflow: hidden;
		cursor: pointer;
		margin-bottom: 8px;
	}

	.toast-notification:focus {
		outline: 2px solid #007acc;
		outline-offset: 2px;
	}

	.toast-notification.visible {
		opacity: 1;
		transform: translateX(0);
	}

	.toast-content {
		display: flex;
		align-items: flex-start;
		padding: 12px 16px;
		gap: 10px;
	}

	.toast-icon {
		flex-shrink: 0;
		width: 18px;
		height: 18px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
		font-weight: bold;
		margin-top: 1px;
	}

	.toast-message {
		flex: 1;
		line-height: 1.4;
		word-break: break-word;
	}

	.toast-close {
		flex-shrink: 0;
		background: transparent;
		border: none;
		color: #888;
		font-size: 18px;
		line-height: 1;
		padding: 0;
		width: 20px;
		height: 20px;
		cursor: pointer;
		border-radius: 3px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: color 0.2s ease, background-color 0.2s ease;
	}

	.toast-close:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.1);
	}

	.toast-close:focus {
		outline: 1px solid #007acc;
		outline-offset: 1px;
	}

	.toast-progress-container {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 3px;
		background: rgba(255, 255, 255, 0.1);
	}

	.toast-progress-bar {
		height: 100%;
		width: 100%;
		transition: width 0.1s linear;
	}

	/* Type-specific styling */
	.toast-info {
		border-left: 4px solid #007acc;
	}
	.toast-info .toast-icon {
		color: #007acc;
	}
	.toast-info .toast-progress-bar {
		background: #007acc;
	}

	.toast-success {
		border-left: 4px solid #4CAF50;
	}
	.toast-success .toast-icon {
		color: #4CAF50;
	}
	.toast-success .toast-progress-bar {
		background: #4CAF50;
	}

	.toast-warning {
		border-left: 4px solid #ffc107;
	}
	.toast-warning .toast-icon {
		color: #ffc107;
	}
	.toast-warning .toast-progress-bar {
		background: #ffc107;
	}

	.toast-error {
		border-left: 4px solid #f44336;
	}
	.toast-error .toast-icon {
		color: #f44336;
	}
	.toast-error .toast-progress-bar {
		background: #f44336;
	}

	/* Hover effects */
	.toast-notification:hover {
		box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
	}

	/* Animation for stacking */
	.toast-notification:not(:last-child) {
		margin-bottom: 8px;
	}

	/* Responsive design */
	@media (max-width: 480px) {
		.toast-notification {
			min-width: 250px;
			max-width: calc(100vw - 40px);
		}

		.toast-content {
			padding: 10px 12px;
		}

		.toast-message {
			font-size: 13px;
		}
	}
</style>