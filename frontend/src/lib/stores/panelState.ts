// Panel State Management Store
// Provides localStorage-based persistence for panel sizes, positions, and open states

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PanelDimensions {
	width?: number;
	height?: number;
	minWidth?: number;
	minHeight?: number;
	maxWidth?: number;
	maxHeight?: number;
}

export interface PanelPosition {
	x: number;
	y: number;
}

export interface PanelState {
	id: string;
	isOpen: boolean;
	dimensions: PanelDimensions;
	position?: PanelPosition; // For floating panels
	lastModified: number;
}

export interface PanelStateStore {
	panels: Record<string, PanelState>;
	version: string; // For migration compatibility
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEY = 'uiagent-panel-state';
const STORAGE_VERSION = '1.0.0';
const DEFAULT_DEBOUNCE_MS = 250;

// Default panel configurations
const DEFAULT_PANELS: Record<string, Partial<PanelState>> = {
	'python-console-output': {
		isOpen: false,
		dimensions: {
			height: 150,
			minHeight: 60,
			maxHeight: 400
		}
	},
	'console-output-floating': {
		isOpen: false,
		dimensions: {
			width: 600,
			height: 300,
			minWidth: 300,
			minHeight: 150
		},
		position: { x: 50, y: 50 }
	},
	'hierarchy-panel': {
		isOpen: true,
		dimensions: {
			width: 350,
			minWidth: 250,
			maxWidth: 600
		}
	},
	'left-panel': {
		isOpen: true,
		dimensions: {
			width: 350,
			minWidth: 300,
			maxWidth: 500
		}
	},
	'middle-panel': {
		isOpen: true,
		dimensions: {
			width: 400,
			minWidth: 300
		}
	}
};

// ─── Storage Utilities ──────────────────────────────────────────────────────

function loadFromStorage(): PanelStateStore {
	if (!browser) {
		return createDefaultStore();
	}

	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (!stored) {
			return createDefaultStore();
		}

		const parsed = JSON.parse(stored) as PanelStateStore;

		// Version check and migration
		if (parsed.version !== STORAGE_VERSION) {
			console.warn(`Panel state version mismatch. Expected ${STORAGE_VERSION}, got ${parsed.version}. Resetting to defaults.`);
			return createDefaultStore();
		}

		// Validate and merge with defaults
		return validateAndMergeStore(parsed);
	} catch (error) {
		console.error('Failed to load panel state from localStorage:', error);
		return createDefaultStore();
	}
}

function saveToStorage(store: PanelStateStore): void {
	if (!browser) return;

	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
	} catch (error) {
		console.error('Failed to save panel state to localStorage:', error);
	}
}

function createDefaultStore(): PanelStateStore {
	const panels: Record<string, PanelState> = {};

	Object.entries(DEFAULT_PANELS).forEach(([id, config]) => {
		panels[id] = {
			id,
			isOpen: config.isOpen ?? true,
			dimensions: config.dimensions ?? {},
			position: config.position,
			lastModified: Date.now()
		};
	});

	return {
		panels,
		version: STORAGE_VERSION
	};
}

function validateAndMergeStore(stored: PanelStateStore): PanelStateStore {
	const merged = { ...stored };

	// Ensure all default panels exist
	Object.entries(DEFAULT_PANELS).forEach(([id, defaultConfig]) => {
		if (!merged.panels[id]) {
			merged.panels[id] = {
				id,
				isOpen: defaultConfig.isOpen ?? true,
				dimensions: defaultConfig.dimensions ?? {},
				position: defaultConfig.position,
				lastModified: Date.now()
			};
		} else {
			// Merge missing dimension constraints
			const existing = merged.panels[id];
			existing.dimensions = {
				...defaultConfig.dimensions,
				...existing.dimensions
			};
		}
	});

	return merged;
}

// ─── Main Store ─────────────────────────────────────────────────────────────

const initialStore = loadFromStorage();
const panelStateStore = writable<PanelStateStore>(initialStore);

// Debounced storage updates
let saveTimeout: ReturnType<typeof setTimeout> | null = null;

function debouncedSave(store: PanelStateStore) {
	if (saveTimeout) {
		clearTimeout(saveTimeout);
	}

	saveTimeout = setTimeout(() => {
		saveToStorage(store);
		saveTimeout = null;
	}, DEFAULT_DEBOUNCE_MS);
}

// Subscribe to changes and persist to localStorage
panelStateStore.subscribe((store) => {
	debouncedSave(store);
});

// ─── Panel State Actions ────────────────────────────────────────────────────

export const panelActions = {
	/**
	 * Get the current state of a specific panel
	 */
	getPanel: (panelId: string): PanelState | null => {
		let currentStore: PanelStateStore;
		panelStateStore.subscribe(store => { currentStore = store; })();
		return currentStore!.panels[panelId] || null;
	},

	/**
	 * Update panel dimensions
	 */
	updateDimensions: (panelId: string, dimensions: Partial<PanelDimensions>) => {
		panelStateStore.update(store => {
			if (!store.panels[panelId]) {
				console.warn(`Panel ${panelId} not found, creating with defaults`);
				store.panels[panelId] = {
					id: panelId,
					isOpen: true,
					dimensions: {},
					lastModified: Date.now()
				};
			}

			const panel = store.panels[panelId];
			panel.dimensions = { ...panel.dimensions, ...dimensions };
			panel.lastModified = Date.now();

			return store;
		});
	},

	/**
	 * Update panel position (for floating panels)
	 */
	updatePosition: (panelId: string, position: PanelPosition) => {
		panelStateStore.update(store => {
			if (!store.panels[panelId]) {
				console.warn(`Panel ${panelId} not found, creating with defaults`);
				store.panels[panelId] = {
					id: panelId,
					isOpen: true,
					dimensions: {},
					lastModified: Date.now()
				};
			}

			const panel = store.panels[panelId];
			panel.position = { ...position };
			panel.lastModified = Date.now();

			return store;
		});
	},

	/**
	 * Toggle panel open state
	 */
	toggleOpen: (panelId: string) => {
		panelStateStore.update(store => {
			if (!store.panels[panelId]) {
				console.warn(`Panel ${panelId} not found, creating with defaults`);
				store.panels[panelId] = {
					id: panelId,
					isOpen: true,
					dimensions: {},
					lastModified: Date.now()
				};
			}

			const panel = store.panels[panelId];
			panel.isOpen = !panel.isOpen;
			panel.lastModified = Date.now();

			return store;
		});
	},

	/**
	 * Set panel open state
	 */
	setOpen: (panelId: string, isOpen: boolean) => {
		panelStateStore.update(store => {
			if (!store.panels[panelId]) {
				console.warn(`Panel ${panelId} not found, creating with defaults`);
				store.panels[panelId] = {
					id: panelId,
					isOpen: true,
					dimensions: {},
					lastModified: Date.now()
				};
			}

			const panel = store.panels[panelId];
			panel.isOpen = isOpen;
			panel.lastModified = Date.now();

			return store;
		});
	},

	/**
	 * Reset a panel to its default state
	 */
	resetPanel: (panelId: string) => {
		const defaultConfig = DEFAULT_PANELS[panelId];
		if (!defaultConfig) {
			console.warn(`No default configuration found for panel ${panelId}`);
			return;
		}

		panelStateStore.update(store => {
			store.panels[panelId] = {
				id: panelId,
				isOpen: defaultConfig.isOpen ?? true,
				dimensions: { ...defaultConfig.dimensions },
				position: defaultConfig.position ? { ...defaultConfig.position } : undefined,
				lastModified: Date.now()
			};

			return store;
		});
	},

	/**
	 * Reset all panels to their default states
	 */
	resetAllPanels: () => {
		panelStateStore.set(createDefaultStore());
	},

	/**
	 * Force save to localStorage (bypasses debouncing)
	 */
	forceSave: () => {
		let currentStore: PanelStateStore;
		panelStateStore.subscribe(store => { currentStore = store; })();
		saveToStorage(currentStore!);
	}
};

// ─── Derived Stores for Individual Panels ──────────────────────────────────

export function createPanelStore(panelId: string) {
	return derived(panelStateStore, (store) => {
		return store.panels[panelId] || null;
	});
}

// ─── Commonly Used Panel Stores ─────────────────────────────────────────────

export const pythonConsoleOutputPanel = createPanelStore('python-console-output');
export const consoleOutputFloatingPanel = createPanelStore('console-output-floating');
export const hierarchyPanel = createPanelStore('hierarchy-panel');
export const leftPanel = createPanelStore('left-panel');
export const middlePanel = createPanelStore('middle-panel');

// ─── Utility Functions ──────────────────────────────────────────────────────

/**
 * Constrain a value within min/max bounds
 */
export function constrainDimension(value: number, min?: number, max?: number): number {
	if (min !== undefined && value < min) return min;
	if (max !== undefined && value > max) return max;
	return value;
}

/**
 * Constrain position within viewport bounds
 */
export function constrainPosition(position: PanelPosition, dimensions: PanelDimensions): PanelPosition {
	if (!browser) return position;

	const maxX = window.innerWidth - (dimensions.width || 300);
	const maxY = window.innerHeight - (dimensions.height || 200);

	return {
		x: Math.max(0, Math.min(position.x, maxX)),
		y: Math.max(0, Math.min(position.y, maxY))
	};
}

/**
 * Get responsive default position for floating panels
 */
export function getResponsivePosition(dimensions: PanelDimensions): PanelPosition {
	if (!browser) return { x: 50, y: 50 };

	const width = dimensions.width || 600;
	const height = dimensions.height || 300;

	// Position in the bottom-right, but with safe margins
	return {
		x: Math.max(50, window.innerWidth - width - 50),
		y: Math.max(50, window.innerHeight - height - 50)
	};
}

// Export the main store
export { panelStateStore };