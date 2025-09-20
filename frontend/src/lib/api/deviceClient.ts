// Device interaction API client
// Provides interface to backend device control endpoints

export interface TapRequest {
    x: number;
    y: number;
    isPercent: boolean;
}

export interface DeviceCommandResponse {
    success: boolean;
    message?: string;
}

/**
 * Send tap command to device at specified coordinates
 * @param serial Device serial number
 * @param x X coordinate (0-1 if isPercent=true, pixels if false)
 * @param y Y coordinate (0-1 if isPercent=true, pixels if false)
 * @param isPercent Whether coordinates are percentages (default: true)
 */
export async function tapDevice(
    serial: string,
    x: number,
    y: number,
    isPercent: boolean = true
): Promise<void> {
    const url = `/api/android/${serial}/command/tap`;
    const body: TapRequest = { x, y, isPercent };

    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(`Device tap failed: ${res.status} ${text}`);
    }
}

/**
 * Send device navigation commands (home, back, recent)
 * @param serial Device serial number
 * @param command Navigation command to send
 */
export async function sendDeviceCommand(
    serial: string,
    command: 'home' | 'back' | 'recent'
): Promise<void> {
    const url = `/api/android/${serial}/command/${command}`;

    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(`Device command '${command}' failed: ${res.status} ${text}`);
    }
}

/**
 * Send long press command to device
 * @param serial Device serial number
 * @param x X coordinate (0-1 if isPercent=true, pixels if false)
 * @param y Y coordinate (0-1 if isPercent=true, pixels if false)
 * @param isPercent Whether coordinates are percentages (default: true)
 */
export async function longPressDevice(
    serial: string,
    x: number,
    y: number,
    isPercent: boolean = true
): Promise<void> {
    const url = `/api/android/${serial}/command/longpress`;
    const body: TapRequest = { x, y, isPercent };

    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(`Device long press failed: ${res.status} ${text}`);
    }
}