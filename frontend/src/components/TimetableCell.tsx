import React from 'react';
import { Tooltip, Typography } from '@mui/material';
import RoomIcon from '@mui/icons-material/Room';
import PersonIcon from '@mui/icons-material/Person';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditNoteIcon from '@mui/icons-material/EditNote';
import ReplayIcon from '@mui/icons-material/Replay';
import { activityTypeColors } from '../hooks/useInstitutionSetup';
import { resolveActivityPresentation } from '../utils/activityPresentation';

// ---------------------------------------------------------------------------
// TimetableSlot — canonical shape returned by GET /api/v1/timetables/view
// ---------------------------------------------------------------------------
export interface TimetableSlot {
    day: string;
    start_time: string;
    end_time: string;
    course_code: string;
    room: string;
    lecturer?: string;
    session_type?: string;
    activity_type_key?: string;
    activity_display_name?: string;
    activity_color?: string;

    // Populated by backend for every slot:
    slot_id?: number;
    timetable_id?: number;
    is_overridden?: boolean;

    // Shared-lecture metadata:
    group_label?: string;
    groups?: string[];
    shared_group_ids?: number[];
    combined_size?: number;
}

// ---------------------------------------------------------------------------
// DragPayload — what we encode into the dataTransfer canvas during drag start.
// Kept flat so JSON serialisation is trivial.
// ---------------------------------------------------------------------------
export interface DragPayload {
    slot_id: number;
    timetable_id: number;
    course_code: string;
    /** Duration in whole minutes — preserved across the drop so end_time is
     *  always derived as start_time + duration, never guessed. */
    duration_minutes: number;
    original_day: string;
    original_start_time: string;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface TimetableCellProps {
    slot?: TimetableSlot;
    onClick?: (slot: TimetableSlot) => void;
    selected?: boolean;
    /** Drag-and-drop is only active when the parent grid is in 'assign' mode */
    dragEnabled?: boolean;
    /** Called when the coordinator clicks the "reset override" button */
    onResetOverride?: (slot: TimetableSlot) => void;
    /**
     * Optional map from activity_type_key → { color } provided by the
     * parent page via useInstitutionSetup().  When present, non-legacy
     * session types (e.g. 'theory', 'clinical_skills') will be rendered
     * with the institution-defined colour rather than the DEFAULT_COLOR.
     */
    activityTypesMap?: Record<string, { color: string; display_name: string }>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function parseHHMM(time: string): number {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + (m ?? 0);
}

const SESSION_COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
    lecture: { bg: '#e3f2fd', border: '#90caf9', text: '#0d47a1' },
    practical: { bg: '#e8f5e9', border: '#a5d6a7', text: '#1b5e20' },
    tutorial: { bg: '#fff3e0', border: '#ffcc80', text: '#e65100' },
};

const DEFAULT_COLOR = { bg: '#f3e5f5', border: '#ce93d8', text: '#4a148c' };

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const TimetableCell: React.FC<TimetableCellProps> = ({
    slot,
    onClick,
    selected,
    dragEnabled = false,
    onResetOverride,
    activityTypesMap,
}) => {
    // ---- Empty cell --------------------------------------------------------
    if (!slot) {
        return <div className="empty-cell" aria-label="No class scheduled" />;
    }

    // ---- Colour by session type --------------------------------------------
    // Priority order:
    //  1. Static legacy map (lecture / practical / tutorial)
    //  2. Dynamic activity type from parent-provided map
    //  3. Generic default (purple tint)
    const activityPresentation = resolveActivityPresentation(slot, activityTypesMap);
    const sessionKey = activityPresentation.key;
    let colors = SESSION_COLOR_MAP[sessionKey];
    if (!colors && activityPresentation.color) {
        colors = activityTypeColors(activityPresentation.color);
    }
    if (!colors) colors = DEFAULT_COLOR;

    // ---- Drag start --------------------------------------------------------
    const handleDragStart = (e: React.DragEvent<HTMLDivElement>) => {
        if (!slot.slot_id || !slot.timetable_id) {
            // Safety: if the backend hasn't returned IDs yet, block initiation
            e.preventDefault();
            return;
        }
        const payload: DragPayload = {
            slot_id: slot.slot_id,
            timetable_id: slot.timetable_id,
            course_code: slot.course_code,
            duration_minutes: parseHHMM(slot.end_time) - parseHHMM(slot.start_time),
            original_day: slot.day,
            original_start_time: slot.start_time,
        };
        e.dataTransfer.setData('application/json', JSON.stringify(payload));
        e.dataTransfer.effectAllowed = 'move';
        // Brief visual feedback: the drag ghost is already the element itself,
        // so we just add a class via a class toggle trick that CSS can pick up.
        // We use setTimeout so the class is applied after the ghost is captured.
        const el = e.currentTarget;
        setTimeout(() => el.classList.add('timetable-cell--dragging'), 0);
    };

    const handleDragEnd = (e: React.DragEvent<HTMLDivElement>) => {
        e.currentTarget.classList.remove('timetable-cell--dragging');
    };

    // ---- Click -------------------------------------------------------------
    const handleClick = (e: React.MouseEvent) => {
        // Don't trigger slot-click when the reset button is pressed
        if ((e.target as HTMLElement).closest('.reset-override-btn')) return;
        if (onClick) onClick(slot);
    };

    // ---- CSS classes -------------------------------------------------------
    const classNames = [
        'timetable-cell',
        onClick ? 'timetable-cell--clickable' : '',
        selected ? 'timetable-cell--selected' : '',
        dragEnabled ? 'timetable-cell--draggable' : '',
        slot.is_overridden ? 'timetable-cell--overridden' : '',
    ]
        .filter(Boolean)
        .join(' ');

    // ---- Render ------------------------------------------------------------
    return (
        <div
            className={classNames}
            role="listitem"
            aria-label={`${slot.course_code} in ${slot.room}`}
            aria-grabbed={dragEnabled ? 'false' : undefined}
            draggable={dragEnabled && !!slot.slot_id}
            onDragStart={dragEnabled ? handleDragStart : undefined}
            onDragEnd={dragEnabled ? handleDragEnd : undefined}
            onClick={handleClick}
            style={{
                backgroundColor: colors.bg,
                borderColor: selected ? '#1565c0' : colors.border,
                borderWidth: selected ? 2 : 1,
                borderStyle: 'solid',
            }}
        >
            {/* Drag handle — only visible in assign mode */}
            {dragEnabled && (
                <div className="drag-handle" aria-hidden="true">
                    <DragIndicatorIcon fontSize="inherit" />
                </div>
            )}

            {/* Override badge */}
            {slot.is_overridden && (
                <Tooltip title="Manually repositioned" arrow placement="top">
                    <div className="override-badge" aria-label="Override active">
                        <EditNoteIcon fontSize="inherit" />
                    </div>
                </Tooltip>
            )}

            {/* Course code */}
            <div className="timetable-cell-code" style={{ color: colors.text }}>
                {slot.course_code}
            </div>

            {/* Session type chip */}
            {slot.session_type && (
                <div
                    className="timetable-cell-session-type"
                    style={{ color: colors.text, opacity: 0.75 }}
                >
                    {activityPresentation.displayName}
                </div>
            )}

            {/* Room */}
            <div className="timetable-cell-meta">
                <RoomIcon />
                <Typography
                    component="span"
                    variant="caption"
                    sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                    {slot.room}
                </Typography>
            </div>

            {/* Lecturer */}
            {slot.lecturer && (
                <div className="timetable-cell-meta">
                    <PersonIcon />
                    <Typography
                        component="span"
                        variant="caption"
                        sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    >
                        {slot.lecturer}
                    </Typography>
                </div>
            )}

            {/* Audience / group label */}
            {slot.group_label && (
                <div className="timetable-cell-meta" style={{ marginTop: '2px' }}>
                    <Typography
                        component="span"
                        variant="caption"
                        sx={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            fontWeight: 600,
                        }}
                    >
                        {slot.group_label}
                    </Typography>
                </div>
            )}

            {/* Shared group badge */}
            {slot.shared_group_ids && slot.shared_group_ids.length > 0 && (
                <div className="timetable-cell-meta" style={{ marginTop: '2px', color: '#1976d2' }}>
                    <Typography component="span" variant="caption" sx={{ fontWeight: 'bold' }}>
                        Shared ({slot.combined_size} students)
                    </Typography>
                </div>
            )}

            {/* Time range footer */}
            <div className="timetable-cell-time">
                {slot.start_time} – {slot.end_time}
            </div>

            {/* Reset override button — only shown when there is an active override */}
            {slot.is_overridden && onResetOverride && (
                <Tooltip title="Reset to solver position" arrow placement="bottom">
                    <button
                        className="reset-override-btn"
                        aria-label="Reset override"
                        onClick={(e) => {
                            e.stopPropagation();
                            onResetOverride(slot);
                        }}
                    >
                        <ReplayIcon fontSize="inherit" />
                    </button>
                </Tooltip>
            )}
        </div>
    );
};

export default TimetableCell;
