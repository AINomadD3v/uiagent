<script lang="ts">
	/**
	 * @file NotificationExamples.svelte
	 * Comprehensive examples and testing interface for the notification system
	 * This component serves as both documentation and a testing tool
	 */

	import { notificationStore, updateMessage } from '$lib/stores/notifications';

	// ─── EXAMPLE DATA ────────────────────────────────────────────────────────────────────────────

	const exampleMessages = {
		info: [
			'Device connected successfully',
			'UI hierarchy refreshed',
			'Screenshot captured',
			'Search completed with 15 results'
		],
		success: [
			'Python code executed successfully',
			'Test automation completed',
			'Settings saved',
			'Device configuration updated'
		],
		warning: [
			'Device disconnected, attempting to reconnect...',
			'Python environment not optimal',
			'Large hierarchy detected (may be slow)',
			'Memory usage is high'
		],
		error: [
			'Failed to execute Python code',
			'Device connection lost',
			'Invalid XPath selector',
			'Network timeout occurred'
		]
	};

	// ─── DEMO METHODS ────────────────────────────────────────────────────────────────────────────

	/**
	 * Shows a random toast notification of the specified type
	 */
	function showRandomToast(type: 'info' | 'success' | 'warning' | 'error', duration = 3000) {
		const messages = exampleMessages[type];
		const message = messages[Math.floor(Math.random() * messages.length)];
		notificationStore.showToast(message, type, duration);
	}

	/**
	 * Shows a random global message of the specified type
	 */
	function showRandomGlobalMessage(type: 'info' | 'success' | 'warning' | 'error', duration = 0) {
		const messages = exampleMessages[type];
		const message = messages[Math.floor(Math.random() * messages.length)];
		notificationStore.updateGlobalMessage(message, type, duration);
	}

	/**
	 * Legacy updateMessage examples
	 */
	function showLegacyMessage(type: 'info' | 'success' | 'warning' | 'error') {
		const messages = exampleMessages[type];
		const message = messages[Math.floor(Math.random() * messages.length)];
		updateMessage(message, type, 5000);
	}

	/**
	 * Shows multiple toast notifications in sequence
	 */
	function showToastSequence() {
		const types = ['info', 'success', 'warning', 'error'] as const;

		types.forEach((type, index) => {
			setTimeout(() => {
				showRandomToast(type, 4000);
			}, index * 500);
		});
	}

	/**
	 * Shows stress test with many notifications
	 */
	function showStressTest() {
		for (let i = 0; i < 8; i++) {
			setTimeout(() => {
				const types = ['info', 'success', 'warning', 'error'] as const;
				const type = types[Math.floor(Math.random() * types.length)];
				showRandomToast(type, 6000);
			}, i * 200);
		}
	}

	/**
	 * Clears all notifications
	 */
	function clearAll() {
		notificationStore.clearAllToasts();
		notificationStore.hideGlobalMessage();
	}
</script>

<div class="notification-examples">
	<h2>🔔 Notification System Examples & Testing</h2>

	<div class="examples-section">
		<h3>Toast Notifications</h3>
		<p>Auto-dismissing notifications that appear in the top-right corner</p>

		<div class="button-group">
			<button class="btn btn-info" on:click={() => showRandomToast('info')}>
				Info Toast
			</button>
			<button class="btn btn-success" on:click={() => showRandomToast('success')}>
				Success Toast
			</button>
			<button class="btn btn-warning" on:click={() => showRandomToast('warning')}>
				Warning Toast
			</button>
			<button class="btn btn-error" on:click={() => showRandomToast('error')}>
				Error Toast
			</button>
		</div>

		<div class="button-group">
			<button class="btn btn-secondary" on:click={() => showRandomToast('info', 0)}>
				Persistent Toast (No Auto-Dismiss)
			</button>
			<button class="btn btn-secondary" on:click={showToastSequence}>
				Show Sequence
			</button>
			<button class="btn btn-secondary" on:click={showStressTest}>
				Stress Test (8 toasts)
			</button>
		</div>
	</div>

	<div class="examples-section">
		<h3>Global Messages</h3>
		<p>Persistent messages that appear at the top of the page</p>

		<div class="button-group">
			<button class="btn btn-info" on:click={() => showRandomGlobalMessage('info')}>
				Global Info
			</button>
			<button class="btn btn-success" on:click={() => showRandomGlobalMessage('success')}>
				Global Success
			</button>
			<button class="btn btn-warning" on:click={() => showRandomGlobalMessage('warning')}>
				Global Warning
			</button>
			<button class="btn btn-error" on:click={() => showRandomGlobalMessage('error')}>
				Global Error
			</button>
		</div>

		<div class="button-group">
			<button class="btn btn-secondary" on:click={() => showRandomGlobalMessage('info', 5000)}>
				Auto-Hide Global (5s)
			</button>
		</div>
	</div>

	<div class="examples-section">
		<h3>Legacy Compatibility</h3>
		<p>Using the legacy updateMessage API</p>

		<div class="button-group">
			<button class="btn btn-info" on:click={() => showLegacyMessage('info')}>
				Legacy Info
			</button>
			<button class="btn btn-success" on:click={() => showLegacyMessage('success')}>
				Legacy Success
			</button>
			<button class="btn btn-warning" on:click={() => showLegacyMessage('warning')}>
				Legacy Warning
			</button>
			<button class="btn btn-error" on:click={() => showLegacyMessage('error')}>
				Legacy Error
			</button>
		</div>
	</div>

	<div class="examples-section">
		<h3>Convenience Methods</h3>
		<p>Using the store's convenience methods</p>

		<div class="button-group">
			<button class="btn btn-info" on:click={() => notificationStore.info('This is an info message')}>
				store.info()
			</button>
			<button class="btn btn-success" on:click={() => notificationStore.success('Operation completed!')}>
				store.success()
			</button>
			<button class="btn btn-warning" on:click={() => notificationStore.warning('Please be careful')}>
				store.warning()
			</button>
			<button class="btn btn-error" on:click={() => notificationStore.error('Something went wrong')}>
				store.error()
			</button>
		</div>

		<div class="button-group">
			<button class="btn btn-info" on:click={() => notificationStore.globalInfo('Global info message')}>
				store.globalInfo()
			</button>
			<button class="btn btn-success" on:click={() => notificationStore.globalSuccess('Global success!')}>
				store.globalSuccess()
			</button>
		</div>
	</div>

	<div class="examples-section">
		<h3>Control Actions</h3>

		<div class="button-group">
			<button class="btn btn-danger" on:click={clearAll}>
				Clear All Notifications
			</button>
			<button class="btn btn-secondary" on:click={() => notificationStore.configure({ maxToasts: 3 })}>
				Set Max Toasts: 3
			</button>
			<button class="btn btn-secondary" on:click={() => notificationStore.configure({ maxToasts: 5 })}>
				Set Max Toasts: 5
			</button>
		</div>
	</div>

	<div class="api-documentation">
		<h3>📚 API Documentation</h3>

		<div class="api-section">
			<h4>Store Methods</h4>
			<pre><code>{`// Toast notifications (auto-dismiss)
notificationStore.showToast(message, type, duration)
notificationStore.info(message, duration?)
notificationStore.success(message, duration?)
notificationStore.warning(message, duration?)
notificationStore.error(message, duration?)

// Global messages (persistent)
notificationStore.showGlobalMessage(message, type, affectsBodyPadding?)
notificationStore.updateGlobalMessage(message, type, duration?)
notificationStore.globalInfo(message, duration?)
notificationStore.globalSuccess(message, duration?)
notificationStore.globalWarning(message, duration?)
notificationStore.globalError(message, duration?)

// Control methods
notificationStore.hideToast(id)
notificationStore.hideGlobalMessage()
notificationStore.clearAllToasts()
notificationStore.configure({ maxToasts?, defaultToastDuration? })
notificationStore.reset()

// Legacy compatibility
updateMessage(text, type, duration) // Maps to global message`}</code></pre>
		</div>

		<div class="api-section">
			<h4>Types</h4>
			<pre><code>{`type NotificationType = 'info' | 'success' | 'warning' | 'error'

interface ToastNotification {
  id: string
  message: string
  type: NotificationType
  timestamp: string
  duration: number
  visible: boolean
}

interface GlobalMessage {
  id: string
  message: string
  type: NotificationType
  timestamp: string
  visible: boolean
  affectsBodyPadding: boolean
}`}</code></pre>
		</div>

		<div class="api-section">
			<h4>Accessibility Features</h4>
			<ul>
				<li><strong>ARIA Support:</strong> Proper role, aria-live, and aria-atomic attributes</li>
				<li><strong>Keyboard Navigation:</strong> Focus support, Escape key dismissal</li>
				<li><strong>Screen Reader:</strong> Assertive announcements for errors, polite for info</li>
				<li><strong>High Contrast:</strong> Respects prefers-contrast media query</li>
				<li><strong>Reduced Motion:</strong> Respects prefers-reduced-motion preference</li>
			</ul>
		</div>

		<div class="api-section">
			<h4>Integration Example</h4>
			<pre><code>{`// In your Svelte component
import { notificationStore } from '$lib/stores/notifications'

// Show notifications
function handleSuccess() {
  notificationStore.success('Operation completed successfully!')
}

function handleError(error: string) {
  notificationStore.error(error, 0) // 0 = no auto-dismiss
}

// Legacy code compatibility
function legacyFunction() {
  updateMessage('Status updated', 'info', 3000)
}`}</code></pre>
		</div>
	</div>
</div>

<style>
	.notification-examples {
		padding: 20px;
		max-width: 1000px;
		margin: 0 auto;
		background: #1e1e1e;
		color: #d4d4d4;
		border-radius: 8px;
		margin-bottom: 20px;
	}

	h2 {
		color: #fff;
		margin-bottom: 20px;
		border-bottom: 2px solid #007acc;
		padding-bottom: 10px;
	}

	h3 {
		color: #fff;
		margin: 25px 0 10px 0;
	}

	h4 {
		color: #007acc;
		margin: 20px 0 10px 0;
	}

	p {
		color: #cccccc;
		margin-bottom: 15px;
		line-height: 1.4;
	}

	.examples-section {
		margin-bottom: 30px;
		padding: 15px;
		background: #252526;
		border-radius: 6px;
		border: 1px solid #3c3c3c;
	}

	.button-group {
		display: flex;
		gap: 10px;
		flex-wrap: wrap;
		margin: 10px 0;
	}

	.btn {
		padding: 8px 16px;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-size: 14px;
		font-weight: 500;
		transition: all 0.2s ease;
		min-width: 120px;
	}

	.btn:hover {
		transform: translateY(-1px);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	}

	.btn-info {
		background: #007acc;
		color: white;
	}
	.btn-info:hover {
		background: #005fab;
	}

	.btn-success {
		background: #4CAF50;
		color: white;
	}
	.btn-success:hover {
		background: #45a049;
	}

	.btn-warning {
		background: #ffc107;
		color: #1e1e1e;
	}
	.btn-warning:hover {
		background: #e0a800;
	}

	.btn-error {
		background: #f44336;
		color: white;
	}
	.btn-error:hover {
		background: #da190b;
	}

	.btn-secondary {
		background: #6c757d;
		color: white;
	}
	.btn-secondary:hover {
		background: #5a6268;
	}

	.btn-danger {
		background: #dc3545;
		color: white;
	}
	.btn-danger:hover {
		background: #c82333;
	}

	.api-documentation {
		margin-top: 40px;
		padding: 20px;
		background: #2d2d2d;
		border-radius: 6px;
		border: 1px solid #4a4a4a;
	}

	.api-section {
		margin-bottom: 25px;
	}

	pre {
		background: #1e1e1e;
		padding: 15px;
		border-radius: 4px;
		overflow-x: auto;
		font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
		font-size: 13px;
		line-height: 1.4;
		border: 1px solid #3c3c3c;
	}

	code {
		color: #d4d4d4;
	}

	ul {
		margin: 10px 0;
		padding-left: 20px;
	}

	li {
		margin: 5px 0;
		line-height: 1.4;
	}

	li strong {
		color: #007acc;
	}

	/* Responsive design */
	@media (max-width: 768px) {
		.notification-examples {
			padding: 15px;
		}

		.button-group {
			flex-direction: column;
		}

		.btn {
			min-width: auto;
			width: 100%;
		}

		pre {
			font-size: 12px;
			padding: 10px;
		}
	}
</style>