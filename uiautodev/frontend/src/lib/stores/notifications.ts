/**
 * @file Global notification system store for SvelteKit frontend
 * Implements comprehensive toast and global message functionality with feature parity to legacy system
 */

import { writable, get } from 'svelte/store';

// ─── TYPE DEFINITIONS ─────────────────────────────────────────────────────────────────────────

/** Supported notification types with color coding */
export type NotificationType = 'info' | 'success' | 'warning' | 'error';

/** Base interface for all notification messages */
export interface BaseNotification {
	/** Unique identifier for this notification */
	id: string;
	/** The notification message text */
	message: string;
	/** The type of notification determining styling and behavior */
	type: NotificationType;
	/** ISO timestamp when notification was created */
	timestamp: string;
}

/** Toast notification that auto-dismisses */
export interface ToastNotification extends BaseNotification {
	/** Duration in milliseconds before auto-dismiss (0 = no auto-dismiss) */
	duration: number;
	/** Whether this toast is currently visible */
	visible: boolean;
}

/** Global message that persists until manually dismissed */
export interface GlobalMessage extends BaseNotification {
	/** Whether this message is currently visible */
	visible: boolean;
	/** Whether this message affects body padding (legacy compatibility) */
	affectsBodyPadding: boolean;
}

/** Complete notification system state */
export interface NotificationState {
	/** Array of active toast notifications */
	toasts: ToastNotification[];
	/** Current global message (only one at a time) */
	globalMessage: GlobalMessage | null;
	/** Maximum number of concurrent toasts to display */
	maxToasts: number;
	/** Default duration for toast notifications */
	defaultToastDuration: number;
}

// ─── DEFAULT STATE ────────────────────────────────────────────────────────────────────────────

const initialState: NotificationState = {
	toasts: [],
	globalMessage: null,
	maxToasts: 5,
	defaultToastDuration: 3000
};

// ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────────────────────

/** Generates a unique notification ID */
function generateId(): string {
	return `notification_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/** Creates an ISO timestamp for the current time */
function createTimestamp(): string {
	return new Date().toISOString();
}

// ─── STORE IMPLEMENTATION ─────────────────────────────────────────────────────────────────────

function createNotificationStore() {
	const { subscribe, update, set } = writable<NotificationState>({ ...initialState });

	return {
		/** Allows Svelte components to subscribe to state changes */
		subscribe,

		// ─── TOAST NOTIFICATIONS ──────────────────────────────────────────────────────────────────

		/**
		 * Shows a toast notification with auto-dismiss
		 * @param message The message to display
		 * @param type The notification type (info, success, warning, error)
		 * @param duration Duration in milliseconds (0 = no auto-dismiss, default = 3000)
		 * @returns The created notification ID
		 */
		showToast: (
			message: string,
			type: NotificationType = 'info',
			duration: number = 0
		): string => {
			const id = generateId();
			const actualDuration = duration || get({ subscribe }).defaultToastDuration;

			update(state => {
				const newToast: ToastNotification = {
					id,
					message,
					type,
					timestamp: createTimestamp(),
					duration: actualDuration,
					visible: false // Will be set to true after DOM update for animation
				};

				// Remove oldest toast if we're at max capacity
				if (state.toasts.length >= state.maxToasts) {
					state.toasts = state.toasts.slice(1);
				}

				state.toasts = [...state.toasts, newToast];
				return state;
			});

			// Show toast after DOM update for slide-in animation
			setTimeout(() => {
				update(state => {
					const toast = state.toasts.find(t => t.id === id);
					if (toast) {
						toast.visible = true;
					}
					return state;
				});
			}, 10);

			// Auto-dismiss if duration > 0
			if (actualDuration > 0) {
				setTimeout(() => {
					hideToast(id);
				}, actualDuration);
			}

			return id;
		},

		/**
		 * Hides a specific toast notification
		 * @param id The notification ID to hide
		 */
		hideToast: (id: string) => {
			update(state => {
				const toast = state.toasts.find(t => t.id === id);
				if (toast) {
					toast.visible = false;
				}
				return state;
			});

			// Remove from array after fade-out animation completes
			setTimeout(() => {
				update(state => {
					state.toasts = state.toasts.filter(t => t.id !== id);
					return state;
				});
			}, 300); // Match CSS transition duration
		},

		/**
		 * Clears all toast notifications immediately
		 */
		clearAllToasts: () => {
			update(state => {
				state.toasts = [];
				return state;
			});
		},

		// ─── GLOBAL MESSAGE AREA ──────────────────────────────────────────────────────────────────

		/**
		 * Shows a global message that persists until manually dismissed
		 * @param message The message to display
		 * @param type The notification type (info, success, warning, error)
		 * @param affectsBodyPadding Whether to add body padding (legacy compatibility)
		 * @returns The created notification ID
		 */
		showGlobalMessage: (
			message: string,
			type: NotificationType = 'info',
			affectsBodyPadding: boolean = true
		): string => {
			const id = generateId();

			update(state => {
				// Clear any existing global message
				if (state.globalMessage && state.globalMessage.affectsBodyPadding) {
					document.body.classList.remove('message-visible');
				}

				const newMessage: GlobalMessage = {
					id,
					message,
					type,
					timestamp: createTimestamp(),
					visible: true,
					affectsBodyPadding
				};

				state.globalMessage = newMessage;

				// Add body padding class if needed (legacy compatibility)
				if (affectsBodyPadding) {
					document.body.classList.add('message-visible');
				}

				return state;
			});

			return id;
		},

		/**
		 * Hides the current global message
		 */
		hideGlobalMessage: () => {
			update(state => {
				if (state.globalMessage) {
					if (state.globalMessage.affectsBodyPadding) {
						document.body.classList.remove('message-visible');
					}
					state.globalMessage = null;
				}
				return state;
			});
		},

		/**
		 * Updates an existing global message (legacy compatibility)
		 * @param message The new message text
		 * @param type The notification type
		 * @param duration Auto-hide duration (0 = no auto-hide)
		 */
		updateGlobalMessage: (
			message: string,
			type: NotificationType = 'info',
			duration: number = 0
		) => {
			const id = showGlobalMessage(message, type, true);

			// Auto-hide if duration specified
			if (duration > 0) {
				setTimeout(() => {
					hideGlobalMessage();
				}, duration);
			}

			return id;
		},

		// ─── CONVENIENCE METHODS ──────────────────────────────────────────────────────────────────

		/** Shows an info toast notification */
		info: (message: string, duration?: number) => showToast(message, 'info', duration),

		/** Shows a success toast notification */
		success: (message: string, duration?: number) => showToast(message, 'success', duration),

		/** Shows a warning toast notification */
		warning: (message: string, duration?: number) => showToast(message, 'warning', duration),

		/** Shows an error toast notification */
		error: (message: string, duration?: number) => showToast(message, 'error', duration),

		/** Shows a global info message */
		globalInfo: (message: string, duration?: number) => updateGlobalMessage(message, 'info', duration),

		/** Shows a global success message */
		globalSuccess: (message: string, duration?: number) => updateGlobalMessage(message, 'success', duration),

		/** Shows a global warning message */
		globalWarning: (message: string, duration?: number) => updateGlobalMessage(message, 'warning', duration),

		/** Shows a global error message */
		globalError: (message: string, duration?: number) => updateGlobalMessage(message, 'error', duration),

		// ─── CONFIGURATION ────────────────────────────────────────────────────────────────────────

		/**
		 * Updates notification system configuration
		 * @param config Partial configuration to update
		 */
		configure: (config: Partial<Pick<NotificationState, 'maxToasts' | 'defaultToastDuration'>>) => {
			update(state => {
				if (config.maxToasts !== undefined) {
					state.maxToasts = Math.max(1, config.maxToasts);
				}
				if (config.defaultToastDuration !== undefined) {
					state.defaultToastDuration = Math.max(100, config.defaultToastDuration);
				}
				return state;
			});
		},

		/**
		 * Resets the notification system to initial state
		 */
		reset: () => {
			// Clean up body classes
			document.body.classList.remove('message-visible');
			set({ ...initialState });
		}
	};
}

// ─── STORE INSTANCE ───────────────────────────────────────────────────────────────────────────

/**
 * The singleton instance of the notification store, exported for use in any component
 * This provides global access to the notification system throughout the application
 */
export const notificationStore = createNotificationStore();

// Make hideToast available for component use
const { hideToast, showGlobalMessage, hideGlobalMessage, updateGlobalMessage } = notificationStore;
export { hideToast, showGlobalMessage, hideGlobalMessage, updateGlobalMessage };

// ─── LEGACY COMPATIBILITY ─────────────────────────────────────────────────────────────────────

/**
 * Legacy updateMessage function for backward compatibility with existing code
 * Maps to the new notification system while maintaining the same API
 * @param text The message text
 * @param type The message type (info, error, warning, success)
 * @param duration Auto-hide duration in milliseconds (3000 default, 0 = no auto-hide)
 */
export function updateMessage(
	text: string,
	type: NotificationType = 'info',
	duration: number = 3000
): void {
	if (duration === 0) {
		// Persistent global message
		notificationStore.showGlobalMessage(text, type, true);
	} else {
		// Global message with auto-hide
		notificationStore.updateGlobalMessage(text, type, duration);
	}
}

// Make updateMessage globally available (legacy compatibility)
if (typeof window !== 'undefined') {
	(window as any).updateMessage = updateMessage;
	(window as any).updateGlobalMessage = updateMessage; // Alternative name
}