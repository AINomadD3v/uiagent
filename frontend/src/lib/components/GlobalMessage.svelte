<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { GlobalMessage } from '$lib/stores/notifications';

	// ─── PROPS ───────────────────────────────────────────────────────────────────────────────────

	/** The global message data to display */
	export let message: GlobalMessage;

	// ─── EVENT DISPATCHER ───────────────────────────────────────────────────────────────────────

	const dispatch = createEventDispatcher<{
		dismiss: { id: string };
	}>();

	// ─── METHODS ─────────────────────────────────────────────────────────────────────────────────

	/**
	 * Handles manual dismissal of the global message
	 */
	function handleDismiss() {
		dispatch('dismiss', { id: message.id });
	}

	/**
	 * Handles keyboard interaction for accessibility
	 */
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			event.preventDefault();
			handleDismiss();
		}
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

	/**
	 * Formats timestamp for display
	 */
	function formatTimestamp(timestamp: string): string {
		const date = new Date(timestamp);
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}
</script>

<div
	class="global-message global-message-{message.type}"
	class:visible={message.visible}
	role={getAriaRole(message.type)}
	aria-live={message.type === 'error' ? 'assertive' : 'polite'}
	aria-atomic="true"
	on:keydown={handleKeydown}
>
	<div class="global-message-content">
		<div class="global-message-icon" aria-hidden="true">
			{getTypeIcon(message.type)}
		</div>
		<div class="global-message-text">
			{message.message}
		</div>
		<div class="global-message-timestamp" title="Message time">
			{formatTimestamp(message.timestamp)}
		</div>
		<button
			class="global-message-close"
			type="button"
			aria-label="Close message"
			title="Close message (Esc)"
			on:click={handleDismiss}
		>
			×
		</button>
	</div>
</div>

<style>
	.global-message {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 9999;
		background: #252526;
		border-bottom: 1px solid #4a4a4a;
		color: #d4d4d4;
		transform: translateY(-100%);
		transition: transform 0.3s ease;
		font-size: 14px;
		min-height: 44px;
		display: flex;
		align-items: center;
	}

	.global-message.visible {
		transform: translateY(0);
	}

	.global-message-content {
		display: flex;
		align-items: center;
		padding: 8px 16px;
		gap: 12px;
		width: 100%;
		max-width: 1200px;
		margin: 0 auto;
	}

	.global-message-icon {
		flex-shrink: 0;
		width: 20px;
		height: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 16px;
		font-weight: bold;
	}

	.global-message-text {
		flex: 1;
		line-height: 1.4;
		word-break: break-word;
	}

	.global-message-timestamp {
		flex-shrink: 0;
		font-size: 12px;
		color: #888;
		font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
	}

	.global-message-close {
		flex-shrink: 0;
		background: transparent;
		border: none;
		color: #888;
		font-size: 20px;
		line-height: 1;
		padding: 4px;
		width: 28px;
		height: 28px;
		cursor: pointer;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: color 0.2s ease, background-color 0.2s ease;
	}

	.global-message-close:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.1);
	}

	.global-message-close:focus {
		outline: 2px solid #007acc;
		outline-offset: 2px;
	}

	/* Type-specific styling */
	.global-message-info {
		background: #1e3a5f;
		border-bottom-color: #007acc;
	}
	.global-message-info .global-message-icon {
		color: #007acc;
	}

	.global-message-success {
		background: #1e3b21;
		border-bottom-color: #4CAF50;
	}
	.global-message-success .global-message-icon {
		color: #4CAF50;
	}

	.global-message-warning {
		background: #3d3319;
		border-bottom-color: #ffc107;
		color: #fff;
	}
	.global-message-warning .global-message-icon {
		color: #ffc107;
	}

	.global-message-error {
		background: #3d1a1a;
		border-bottom-color: #f44336;
	}
	.global-message-error .global-message-icon {
		color: #f44336;
	}

	/* Responsive design */
	@media (max-width: 768px) {
		.global-message-content {
			padding: 8px 12px;
			gap: 8px;
		}

		.global-message-text {
			font-size: 13px;
		}

		.global-message-timestamp {
			display: none; /* Hide timestamp on mobile for space */
		}

		.global-message-icon {
			width: 18px;
			height: 18px;
			font-size: 14px;
		}
	}

	/* Animation for multiple messages (if we ever support them) */
	.global-message:not(:last-child) {
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	/* Legacy compatibility - body padding class */
	:global(body.message-visible) {
		padding-top: 44px;
	}

	/* Adjust for mobile */
	@media (max-width: 768px) {
		:global(body.message-visible) {
			padding-top: 40px;
		}
	}
</style>