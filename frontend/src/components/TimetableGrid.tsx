/**
 * TimetableGrid.tsx
 *
 * Renders a timetable grid using the configured day/time window with first-class
 * drag-and-drop override support.
 *
 * Architecture
 * ─────────────
 * The grid maintains a `localOverrides` map in component state. This is the
 * single source of truth for the UI position of every slot. On mount it is
 * hydrated from the `slots` prop (which already has server-applied overrides
 * baked in as `is_overridden: true`). When the coordinator drags a slot to a
 * new cell the following happens in sequence:
 *
 *   1. `localOverrides` is updated immediately (optimistic UI).
 *   2. A POST /api/v1/timetables/{id}/overrides call is fired asynchronously.
 *   3a. On success → nothing more to do; the override is now persisted and the
 *       next full fetch will return the slot in its new position.
 *   3b. On failure → `localOverrides` is rolled back to `previousOverrides`
 *       and a brief "shake" animation is applied to the target cell to signal
 *       rejection.
 *
 * The grid never rewrites the base `slots` prop; it treats it as immutable
 * during a single view session. This means the drag UX is never blocked by
 * network latency.
 *
 * Agent Beta boundary
 * ───────────────────
 * This file manages its own API calls for the override layer. It intentionally
 * does NOT call the parent fetchTimetable() callback on every drop in order to
 * avoid a full re-render cycle. The parent's data stays consistent; only the
 * local overlay changes.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
    Box,
    Paper,
    Snackbar,
    Alert,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from '@mui/material';
import TimetableCell, { DragPayload, TimetableSlot } from './TimetableCell';
import api from '../api';
import '../styles/TimetableGrid.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TimetableGridMode = 'view' | 'assign';

interface TimetableGridProps {
    slots: TimetableSlot[];
    gridConfig?: {
        start_time?: string;
        end_time?: string;
        active_days?: string[];
    };
    mode?: TimetableGridMode;
    onSlotClick?: (slot: TimetableSlot) => void;
    selectedSlot?: TimetableSlot | null;
    showCurrentTime?: boolean;
    activityTypesMap?: Record<string, { color: string; display_name: string }>;
    /** Called when an override is successfully persisted or reset */
    onOverrideChange?: () => void;
}

/**
 * LocalOverride mirrors the fields changed by a drag operation.
 * It is keyed by slot_id.
 */
interface LocalOverride {
    day: string;
    start_time: string;
    end_time: string;
}

type OverrideMap = Record<number, LocalOverride>;

/** What the drop target cell passes to the drop handler */
interface DropTarget {
    day: string;
    time: string; // "HH:MM" — the row's start time
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY'];

const DAY_LABELS: Record<string, string> = {
    MONDAY: 'Monday',
    TUESDAY: 'Tuesday',
    WEDNESDAY: 'Wednesday',
    THURSDAY: 'Thursday',
    FRIDAY: 'Friday',
    SATURDAY: 'Saturday',
    SUNDAY: 'Sunday',
};

const DEFAULT_TIME_SLOTS = [
    '07:00', '08:00', '09:00', '10:00', '11:00',
    '12:00', '13:00', '14:00', '15:00', '16:00',
    '17:00', '18:00',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function minutesToHHMM(totalMinutes: number): string {
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function parseHHMM(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + (m ?? 0);
}

/**
 * Build a grid lookup: day → start_time → slot.
 * Merges base slots with any local overrides so that:
 *  - A slot that has been overridden appears at its NEW position.
 *  - Its OLD position is vacated.
 */
function buildGrid(
    slots: TimetableSlot[],
    overrides: OverrideMap,
): Record<string, Record<string, TimetableSlot[]>> {
    const grid: Record<string, Record<string, TimetableSlot[]>> = {};

    for (const slot of slots) {
        if (!slot.slot_id) continue;

        const override = overrides[slot.slot_id];
        const effectiveDay = (override?.day ?? slot.day).toUpperCase();
        const effectiveStart = override?.start_time ?? slot.start_time;
        const effectiveEnd = override?.end_time ?? slot.end_time;

        // Build an augmented slot so TimetableCell always receives correct data
        const displaySlot: TimetableSlot = {
            ...slot,
            day: effectiveDay,
            start_time: effectiveStart,
            end_time: effectiveEnd,
            is_overridden: override != null ? true : slot.is_overridden,
        };

        if (!grid[effectiveDay]) grid[effectiveDay] = {};

        // Normalise to the HH:00 key for row matching.
        // If a slot starts at say 08:30 it aligns to the 08:00 row.
        const rowKey = effectiveStart.substring(0, 5);
        grid[effectiveDay][rowKey] = grid[effectiveDay][rowKey] ?? [];
        grid[effectiveDay][rowKey].push(displaySlot);
    }

    return grid;
}

function buildTimeSlots(startTime?: string, endTime?: string): string[] {
    if (!startTime || !endTime) {
        return DEFAULT_TIME_SLOTS;
    }

    const startMinutes = parseHHMM(startTime);
    const endMinutes = parseHHMM(endTime);
    if (Number.isNaN(startMinutes) || Number.isNaN(endMinutes) || endMinutes <= startMinutes) {
        return DEFAULT_TIME_SLOTS;
    }

    const slots: string[] = [];
    for (let minutes = startMinutes; minutes < endMinutes; minutes += 60) {
        slots.push(minutesToHHMM(minutes));
    }
    return slots.length > 0 ? slots : DEFAULT_TIME_SLOTS;
}

function isSameSlot(
    a: TimetableSlot | null | undefined,
    b: TimetableSlot | null | undefined,
): boolean {
    if (!a || !b) return false;
    if (a.slot_id && b.slot_id) return a.slot_id === b.slot_id;
    return (
        a.day === b.day &&
        a.start_time === b.start_time &&
        a.end_time === b.end_time &&
        a.course_code === b.course_code &&
        a.room === b.room
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const TimetableGrid: React.FC<TimetableGridProps> = ({
    slots,
    gridConfig,
    mode = 'view',
    onSlotClick,
    selectedSlot,
    showCurrentTime = false,
    activityTypesMap,
    onOverrideChange,
}) => {
    const isAssignMode = mode === 'assign';
    const configuredDays = gridConfig?.active_days?.map((day) => day.toUpperCase()).filter((day) => day in DAY_LABELS) ?? [];
    const days = configuredDays.length > 0 ? configuredDays : DEFAULT_DAYS;
    const timeSlots = buildTimeSlots(gridConfig?.start_time, gridConfig?.end_time);
    const gridEndMinutes = parseHHMM(gridConfig?.end_time ?? '19:00');

    // ── Local override state ────────────────────────────────────────────────
    /**
     * Seed localOverrides from the base slots prop on first render and whenever
     * the parent refreshes the slot list (e.g., after a full re-fetch).
     * Slots that the backend already baked in as `is_overridden: true` should
     * be reflected immediately.
     */
    const [localOverrides, setLocalOverrides] = useState<OverrideMap>(() => {
        const init: OverrideMap = {};
        for (const s of slots) {
            if (s.is_overridden && s.slot_id) {
                init[s.slot_id] = {
                    day: s.day,
                    start_time: s.start_time,
                    end_time: s.end_time,
                };
            }
        }
        return init;
    });

    // Re-sync if the parent gives us a brand new slots array (e.g. after year change)
    useEffect(() => {
        const init: OverrideMap = {};
        for (const s of slots) {
            if (s.is_overridden && s.slot_id) {
                init[s.slot_id] = {
                    day: s.day,
                    start_time: s.start_time,
                    end_time: s.end_time,
                };
            }
        }
        setLocalOverrides(init);
    }, [slots]);

    // ── Drag-over target tracking ───────────────────────────────────────────
    /** Tracks which cell is currently the drag-over target for highlight */
    const [dropTargetKey, setDropTargetKey] = useState<string | null>(null);

    /** Tracks which cell is playing the shake rejection animation */
    const [shakingKey, setShakingKey] = useState<string | null>(null);

    // ── Toast notifications ─────────────────────────────────────────────────
    const [toast, setToast] = useState<{
        open: boolean;
        message: string;
        severity: 'success' | 'error' | 'warning';
    }>({ open: false, message: '', severity: 'success' });

    const showToast = (message: string, severity: 'success' | 'error' | 'warning') => {
        setToast({ open: true, message, severity });
    };

    const closeToast = (_: React.SyntheticEvent | Event, reason?: string) => {
        if (reason === 'clickaway') return;
        setToast((t) => ({ ...t, open: false }));
    };

    // ── Drop handler ────────────────────────────────────────────────────────
    const handleDrop = useCallback(
        async (e: React.DragEvent<HTMLTableCellElement>, target: DropTarget) => {
            e.preventDefault();
            setDropTargetKey(null);

            // 1. Parse the drag payload
            let payload: DragPayload;
            try {
                payload = JSON.parse(e.dataTransfer.getData('application/json'));
            } catch {
                showToast('Invalid drag data — drop cancelled.', 'error');
                return;
            }

            const { slot_id, timetable_id, duration_minutes } = payload;

            // 2. Ignore no-op drops (same position)
            const newStartMinutes = parseHHMM(target.time);
            const newEndMinutes = newStartMinutes + duration_minutes;
            const newStartStr = minutesToHHMM(newStartMinutes);
            const newEndStr = minutesToHHMM(newEndMinutes);

            const currentOverride = localOverrides[slot_id];
            const baseSlot = slots.find((s) => s.slot_id === slot_id);
            const currentDay = currentOverride?.day ?? baseSlot?.day ?? '';
            const currentStart = currentOverride?.start_time ?? baseSlot?.start_time ?? '';

            if (
                target.day.toUpperCase() === currentDay.toUpperCase() &&
                newStartStr === currentStart
            ) {
                return; // dropped in place — skip network call
            }

            // 3. Validate: block if end_time would exceed the configured grid boundary
            if (newEndMinutes > gridEndMinutes) {
                const cellKey = `${target.day}-${target.time}`;
                setShakingKey(cellKey);
                setTimeout(() => setShakingKey(null), 600);
                showToast(`Cannot drop — session would extend beyond ${minutesToHHMM(gridEndMinutes)}.`, 'warning');
                return;
            }

            // 4. Optimistic update
            const previousOverrides = { ...localOverrides };
            const newOverride: LocalOverride = {
                day: target.day.toUpperCase(),
                start_time: newStartStr,
                end_time: newEndStr,
            };
            setLocalOverrides((prev) => ({ ...prev, [slot_id]: newOverride }));

            // 5. Persist to backend
            try {
                await api.post(`/timetables/${timetable_id}/overrides`, {
                    overrides: [
                        {
                            slot_id,
                            day: newOverride.day,
                            start_time: newOverride.start_time,
                            end_time: newOverride.end_time,
                        },
                    ],
                });
                showToast('Slot moved successfully.', 'success');
                onOverrideChange?.();
            } catch (err: unknown) {
                // 6. Rollback on failure
                setLocalOverrides(previousOverrides);
                const detail =
                    (err as { response?: { data?: { detail?: string } } })
                        ?.response?.data?.detail ?? 'Server error — drop was not saved.';
                const errMsg = typeof detail === 'string' ? detail : JSON.stringify(detail);
                const cellKey = `${target.day}-${target.time}`;
                setShakingKey(cellKey);
                setTimeout(() => setShakingKey(null), 600);
                showToast(errMsg, 'error');
            }
        },
        [gridEndMinutes, localOverrides, slots, onOverrideChange],
    );

    // ── Reset override handler ──────────────────────────────────────────────
    const handleResetOverride = useCallback(
        async (slot: TimetableSlot) => {
            if (!slot.slot_id || !slot.timetable_id) return;

            const previousOverrides = { ...localOverrides };
            // Optimistic: remove from local state immediately
            setLocalOverrides((prev) => {
                const next = { ...prev };
                delete next[slot.slot_id!];
                return next;
            });

            try {
                await api.delete(
                    `/timetables/${slot.timetable_id}/overrides/${slot.slot_id}`,
                );
                showToast('Slot reset to solver position.', 'success');
                onOverrideChange?.();
            } catch {
                setLocalOverrides(previousOverrides);
                showToast('Failed to reset override — please try again.', 'error');
            }
        },
        [localOverrides, onOverrideChange],
    );

    // ── Grid render ─────────────────────────────────────────────────────────
    const grid = buildGrid(slots, localOverrides);

    // Current-time markers
    const now = new Date();
    const currentDayName = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'][now.getDay()];
    const currentHour = now.getHours();

    return (
        <>
            <TableContainer
                component={Paper}
                className="timetable-container"
                aria-label="Timetable grid"
            >
                <Table className="timetable-grid" size="small" stickyHeader={false}>
                    <TableHead>
                        <TableRow>
                            <TableCell className="time-header-cell">Time</TableCell>
                            {days.map((day) => (
                                <TableCell
                                    key={day}
                                    align="center"
                                    className="day-header-cell"
                                >
                                    {DAY_LABELS[day]}
                                </TableCell>
                            ))}
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {timeSlots.map((time) => (
                            <TableRow key={time}>
                                <TableCell className="time-cell">{time}</TableCell>

                                {days.map((day) => {
                                    const cellSlots = grid[day]?.[time] ?? [];
                                    const cellKey = `${day}-${time}`;

                                    // Live-time highlighting
                                    const isCurrentDay = showCurrentTime && day === currentDayName;
                                    const isCurrentHour =
                                        showCurrentTime && currentHour === parseInt(time, 10);
                                    const isLiveActive = isCurrentDay && isCurrentHour;

                                    // Drop-zone state
                                    const isDropTarget = isAssignMode && dropTargetKey === cellKey;
                                    const isShaking = shakingKey === cellKey;

                                    return (
                                        <TableCell
                                            key={cellKey}
                                            className={[
                                                'slot-cell',
                                                isDropTarget ? 'slot-cell--drop-target' : '',
                                                isShaking ? 'slot-cell--shake' : '',
                                            ]
                                                .filter(Boolean)
                                                .join(' ')}
                                            role="gridcell"
                                            // ── Drop zone wiring ──────────
                                            onDragOver={
                                                isAssignMode
                                                    ? (e) => {
                                                          e.preventDefault();
                                                          e.dataTransfer.dropEffect = 'move';
                                                          setDropTargetKey(cellKey);
                                                      }
                                                    : undefined
                                            }
                                            onDragLeave={
                                                isAssignMode
                                                    ? () => {
                                                          if (dropTargetKey === cellKey) {
                                                              setDropTargetKey(null);
                                                          }
                                                      }
                                                    : undefined
                                            }
                                            onDrop={
                                                isAssignMode
                                                    ? (e) => handleDrop(e, { day, time })
                                                    : undefined
                                            }
                                            sx={{
                                                border: isLiveActive
                                                    ? '2px solid #ff4081'
                                                    : undefined,
                                                position: 'relative',
                                                bgcolor: isCurrentDay
                                                    ? 'rgba(0,0,0,0.01)'
                                                    : 'inherit',
                                                transition: 'all 0.2s ease',
                                            }}
                                        >
                                            {/* Live-time bar */}
                                            {isLiveActive && (
                                                <Box
                                                    sx={{
                                                        position: 'absolute',
                                                        top: 0,
                                                        left: 0,
                                                        right: 0,
                                                        height: '4px',
                                                        bgcolor: '#ff4081',
                                                        borderRadius: '4px 4px 0 0',
                                                        zIndex: 10,
                                                        boxShadow:
                                                            '0 0 10px rgba(255, 64, 129, 0.5)',
                                                    }}
                                                />
                                            )}

                                            {cellSlots.length === 0 ? (
                                                <TimetableCell />
                                            ) : (
                                                <Box className="slot-cell-stack">
                                                    {cellSlots.map((slot) => (
                                                        <TimetableCell
                                                            key={slot.slot_id ?? `${slot.course_code}-${slot.start_time}-${slot.room}`}
                                                            slot={slot}
                                                            onClick={
                                                                isAssignMode && slot ? onSlotClick : undefined
                                                            }
                                                            selected={isSameSlot(slot, selectedSlot ?? undefined)}
                                                            dragEnabled={isAssignMode}
                                                            activityTypesMap={activityTypesMap}
                                                            onResetOverride={
                                                                isAssignMode ? handleResetOverride : undefined
                                                            }
                                                        />
                                                    ))}
                                                </Box>
                                            )}
                                        </TableCell>
                                    );
                                })}
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Toast feedback for drag-and-drop operations */}
            <Snackbar
                open={toast.open}
                autoHideDuration={3500}
                onClose={closeToast}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert
                    onClose={closeToast}
                    severity={toast.severity}
                    variant="filled"
                    sx={{ width: '100%' }}
                >
                    {toast.message}
                </Alert>
            </Snackbar>
        </>
    );
};

export default TimetableGrid;
