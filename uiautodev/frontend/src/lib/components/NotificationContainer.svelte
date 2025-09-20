<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { notificationStore, hideToast } from '$lib/stores/notifications';
	import type { NotificationState } from '$lib/stores/notifications';
	import ToastNotification from './ToastNotification.svelte';
	import GlobalMessage from './GlobalMessage.svelte';

	// ─── COMPONENT STATE ─────────────────────────────────────────────────────────────────────────

	let notificationState: NotificationState;
	let unsubscribe: (() => void) | null = null;

	// ─── LIFECYCLE ───────────────────────────────────────────────────────────────────────────────

	onMount(() => {
		// Subscribe to notification store changes
		unsubscribe = notificationStore.subscribe(state => {
			notificationState = state;
		});
	});

	onDestroy(() => {
		if (unsubscribe) {
			unsubscribe();
		}
	});

	// ─── EVENT HANDLERS ──────────────────────────────────────────────────────────────────────────

	/**
	 * Handles toast dismissal events
	 */
	function handleToastDismiss(event: CustomEvent<{ id: string }>) {
		notificationStore.hideToast(event.detail.id);
	}

	/**
	 * Handles global message dismissal events
	 */
	function handleGlobalMessageDismiss(event: CustomEvent<{ id: string }>) {
		notificationStore.hideGlobalMessage();
	}

	// ─── COMPUTED PROPERTIES ─────────────────────────────────────────────────────────────────────

	$: hasToasts = notificationState?.toasts && notificationState.toasts.length > 0;
	$: hasGlobalMessage = notificationState?.globalMessage && notificationState.globalMessage.visible;
</script>

<!-- Toast Container -->
{#if hasToasts}
	<div class="toast-container" role="region" aria-label="Notifications">
		{#each notificationState.toasts as toast (toast.id)}
			<ToastNotification
				{toast}
				on:dismiss={handleToastDismiss}
				on:close={handleToastDismiss}
			/>
		{/each}
	</div>
{/if}

<!-- Global Message -->
{#if hasGlobalMessage}
	<GlobalMessage
		message={notificationState.globalMessage}
		on:dismiss={handleGlobalMessageDismiss}
	/>
{/if}

<style>
	.toast-container {
		position: fixed;
		top: 60px; /* Below header and global message */
		right: 20px;
		z-index: 10000;
		display: flex;
		flex-direction: column;
		gap: 8px;
		pointer-events: none; /* Allow clicks to pass through container */
		max-height: calc(100vh - 80px);
		overflow: hidden;
	}

	.toast-container :global(.toast-notification) {
		pointer-events: auto; /* Re-enable clicks on individual toasts */
	}

	/* Adjust toast position when global message is visible */
	:global(body.message-visible) .toast-container {
		top: 104px; /* Header + global message */
	}

	/* Responsive adjustments */
	@media (max-width: 768px) {
		.toast-container {
			top: 50px;
			right: 10px;
			left: 10px;
			align-items: stretch;
		}

		:global(body.message-visible) .toast-container {
			top: 90px;
		}

		.toast-container :global(.toast-notification) {
			max-width: none;
			min-width: auto;
		}
	}

	/* High contrast mode support */
	@media (prefers-contrast: high) {
		.toast-container :global(.toast-notification) {
			border-width: 2px;
		}
	}

	/* Reduced motion support */
	@media (prefers-reduced-motion: reduce) {
		.toast-container :global(.toast-notification) {
			transition: opacity 0.1s ease;
			transform: none;
		}

		:global(.global-message) {
			transition: none;
			transform: none;
		}
	}

	/* Focus management for screen readers */
	.toast-container:focus-within {
		/* Ensure focused toasts are visible */
		z-index: 10001;
	}
</style>