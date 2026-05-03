import React, { useState, useEffect } from 'react';
import {
    Autocomplete,
    Box,
    Chip,
    CircularProgress,
    InputAdornment,
    TextField,
    Typography,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { debounce } from '@mui/material/utils';
import { formatGroupName, formatPersonName, formatRoomName } from '../utils/displayFormatters';

interface SearchResult {
    type: 'course' | 'lecturer' | 'room' | 'group';
    id: number;
    primary: string;
    secondary: string;
}

const GlobalSearch: React.FC = () => {
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [options, setOptions] = useState<SearchResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [inputValue, setInputValue] = useState('');

    const searchGlobal = async (query: string) => {
        if (query.length < 2) {
            setOptions([]);
            return;
        }

        setLoading(true);
        try {
            const response = await api.get('/search/', {
                params: { q: query, limit: 20 },
            });

            const results: SearchResult[] = [];

            // Add courses
            response.data.courses.forEach((course: any) => {
                results.push({
                    type: 'course',
                    id: course.id,
                    primary: `${course.code} - ${course.title}`,
                    secondary: `Year ${course.year} • ${course.credits} credits`,
                });
            });

            // Add lecturers
            response.data.lecturers.forEach((lecturer: any) => {
                results.push({
                    type: 'lecturer',
                    id: lecturer.id,
                    primary: formatPersonName(lecturer.full_name),
                    secondary: `${lecturer.staff_number} • ${lecturer.email}`,
                });
            });

            // Add rooms
            response.data.rooms.forEach((room: any) => {
                results.push({
                    type: 'room',
                    id: room.id,
                    primary: `${formatRoomName(room.room_number)} - ${room.building}`,
                    secondary: `Capacity: ${room.capacity} • ${room.category}`,
                });
            });

            // Add groups
            response.data.groups.forEach((group: any) => {
                results.push({
                    type: 'group',
                    id: group.id,
                    primary: formatGroupName(group.name, group.display_code),
                    secondary: `Year ${group.year} • ${group.program} • ${group.size} students`,
                });
            });

            setOptions(results);
        } catch (err) {
            console.error('Search error:', err);
            setOptions([]);
        } finally {
            setLoading(false);
        }
    };

    const debouncedSearch = debounce(searchGlobal, 300);

    useEffect(() => {
        if (inputValue) {
            debouncedSearch(inputValue);
        } else {
            setOptions([]);
        }
    }, [inputValue]);

    const handleSelect = (result: SearchResult | null) => {
        if (!result) return;

        // Navigate based on entity type
        switch (result.type) {
            case 'course':
                navigate('/courses');
                break;
            case 'lecturer':
                navigate('/lecturers');
                break;
            case 'room':
                navigate('/rooms');
                break;
            case 'group':
                navigate('/groups');
                break;
        }

        // Clear search
        setInputValue('');
        setOptions([]);
    };

    const getChipColor = (type: string) => {
        switch (type) {
            case 'course':
                return 'primary';
            case 'lecturer':
                return 'secondary';
            case 'room':
                return 'success';
            case 'group':
                return 'warning';
            default:
                return 'default';
        }
    };

    return (
        <Autocomplete
            open={open}
            onOpen={() => setOpen(true)}
            onClose={() => setOpen(false)}
            options={options}
            loading={loading}
            inputValue={inputValue}
            onInputChange={(_, newValue) => setInputValue(newValue)}
            onChange={(_, value) => handleSelect(value)}
            getOptionLabel={(option) => option.primary}
            isOptionEqualToValue={(option, value) => option.id === value.id && option.type === value.type}
            renderInput={(params) => (
                <TextField
                    {...params}
                    placeholder="Search courses, lecturers, rooms..."
                    size="small"
                    sx={{
                        minWidth: 300,
                        '& .MuiOutlinedInput-root': {
                            bgcolor: 'rgba(255, 255, 255, 0.95)',
                            color: '#1a1a1a',
                            borderRadius: '8px',
                            '& fieldset': {
                                borderColor: '#006837',
                                borderWidth: '1.5px',
                                transition: 'all 0.2s ease',
                            },
                            '&:hover fieldset': {
                                borderColor: '#FDB913',
                                borderWidth: '1.5px',
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: '#006837',
                                borderWidth: '2px',
                                boxShadow: '0 0 0 3px rgba(0, 104, 55, 0.1)',
                            },
                        },
                        '& .MuiInputBase-input': {
                            color: '#1a1a1a',
                            fontWeight: 500,
                        },
                        '& .MuiInputBase-input::placeholder': {
                            color: 'rgba(0, 0, 0, 0.5)',
                            opacity: 1,
                        },
                    }}
                    InputProps={{
                        ...params.InputProps,
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon sx={{ color: '#006837' }} />
                            </InputAdornment>
                        ),
                        endAdornment: (
                            <>
                                {loading ? <CircularProgress sx={{ color: '#006837' }} size={20} /> : null}
                                {params.InputProps.endAdornment}
                            </>
                        ),
                    }}
                />
            )}
            renderOption={(props, option) => (
                <Box component="li" {...props} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', py: 1.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Chip
                            label={option.type}
                            size="small"
                            color={getChipColor(option.type) as any}
                            sx={{ textTransform: 'capitalize' }}
                        />
                        <Typography variant="body2" fontWeight="medium">
                            {option.primary}
                        </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary" sx={{ pl: 7 }}>
                        {option.secondary}
                    </Typography>
                </Box>
            )}
            noOptionsText={inputValue.length < 2 ? "Type at least 2 characters" : "No results found"}
            sx={{ flexGrow: 1, maxWidth: 500 }}
        />
    );
};

export default GlobalSearch;
