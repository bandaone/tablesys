import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Alert,
  Chip,
  MenuItem,
} from '@mui/material';
import { Upload as UploadIcon, Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon, DeleteSweep as DeleteSweepIcon } from '@mui/icons-material';
import { roomsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

interface Room {
  id: number;
  room_number: string;
  building: string;
  capacity: number;
  room_type: string;
  equipment: string[];
}

const RoomsPage: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [openDialog, setOpenDialog] = useState(false);

  // Bulk Upload State
  const [openBulkDialog, setOpenBulkDialog] = useState(false);
  const [bulkFile, setBulkFile] = useState<File | null>(null);

  const [editingRoom, setEditingRoom] = useState<Room | null>(null);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    room_number: '',
    building: '',
    capacity: 30,
    room_type: 'lecture_hall',
    room_category: 'lecture_hall_medium',
    department_affinity: '',
    equipment: '',
  });

  const { isCoordinator } = useAuth();

  // Align with Backend Enums
  const roomTypes = [
    { value: 'lecture_hall', label: 'Lecture Hall' },
    { value: 'drawing_room', label: 'Drawing Room' },
    { value: 'seminar_room', label: 'Seminar Room' },
    { value: 'lab', label: 'Laboratory' },
    { value: 'surveying_room', label: 'Surveying Room' },
  ];

  const roomCategories = [
    { value: 'lecture_hall_large', label: 'Large Lecture Hall (>100)' },
    { value: 'lecture_hall_medium', label: 'Medium Lecture Hall (50-100)' },
    { value: 'lecture_hall_small', label: 'Small Lecture Hall (<50)' },
    { value: 'computer_lab', label: 'Computer Lab' },
    { value: 'mechanical_lab', label: 'Mechanical Lab' },
    { value: 'electrical_lab', label: 'Electrical Lab' },
    { value: 'drawing_room', label: 'Drawing Room' },
  ];

  useEffect(() => {
    void fetchRooms();
  }, []);

  const fetchRooms = async () => {
    try {
      const data = await roomsAPI.getAll();
      setRooms(data);
    } catch (err) {
      setError('Failed to load rooms');
    }
  };

  const handleOpenDialog = (room?: Room) => {
    if (room) {
      setEditingRoom(room);
      setFormData({
        room_number: room.room_number,
        building: room.building,
        capacity: room.capacity,
        room_type: room.room_type,
        room_category: (room as any).room_category || 'lecture_hall_medium',
        department_affinity: (room as any).department_affinity || '',
        equipment: room.equipment.join(', '),
      });
    } else {
      setEditingRoom(null);
      setFormData({
        room_number: '',
        building: '',
        capacity: 30,
        room_type: 'lecture_hall',
        room_category: 'lecture_hall_medium',
        department_affinity: '',
        equipment: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingRoom(null);
    setError('');
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        ...formData,
        equipment: formData.equipment.split(',').map(e => e.trim()).filter(e => e.length > 0),
      };

      if (editingRoom) {
        await roomsAPI.update(editingRoom.id, payload);
      } else {
        await roomsAPI.create(payload);
      }
      await fetchRooms();
      handleCloseDialog();
    } catch (err) {
      setError('Failed to save room');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this room?')) {
      try {
        await roomsAPI.delete(id);
        await fetchRooms();
      } catch (err) {
        setError('Failed to delete room');
      }
    }
  };

  const handleDeleteAll = async () => {
    if (window.confirm('ARE YOU SURE? This will delete ALL rooms. This action cannot be undone.')) {
      try {
        await roomsAPI.deleteAll();
        await fetchRooms();
        setError(''); // Clear any previous errors
      } catch (err) {
        setError('Failed to delete all rooms');
      }
    }
  };

  const handleBulkUpload = async () => {
    if (!bulkFile) return;
    try {
      const formData = new FormData();
      formData.append('file', bulkFile);
      await roomsAPI.bulkUpload(formData);
      setOpenBulkDialog(false);
      setBulkFile(null);
      await fetchRooms();
    } catch (err) {
      setError('Failed to upload rooms');
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Rooms
        </Typography>
        {isCoordinator && (
          <Box>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteSweepIcon />}
              onClick={() => { void handleDeleteAll(); }}
              sx={{ mr: 2 }}
            >
              Delete All
            </Button>
            <Button
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={() => { setOpenBulkDialog(true); }}
              sx={{ mr: 2 }}
            >
              Bulk Upload
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => { handleOpenDialog(); }}
            >
              Add Room
            </Button>
          </Box>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Room Number</strong></TableCell>
              <TableCell><strong>Building</strong></TableCell>
              <TableCell><strong>Type</strong></TableCell>
              <TableCell><strong>Capacity</strong></TableCell>
              <TableCell><strong>Equipment</strong></TableCell>
              {isCoordinator && <TableCell align="center"><strong>Actions</strong></TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {rooms.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                  <Typography variant="body1" color="text.secondary">
                    No rooms found. Click "Add Room" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rooms.map((room) => (
                <TableRow key={room.id} hover>
                  <TableCell>{room.room_number}</TableCell>
                  <TableCell>{room.building}</TableCell>
                  <TableCell>
                    <Chip label={room.room_type} color="primary" size="small" />
                  </TableCell>
                  <TableCell>{room.capacity}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {room.equipment.map((eq, idx) => (
                        <Chip key={idx} label={eq} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </TableCell>
                  {isCoordinator && (
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => { handleOpenDialog(room); }}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => { void handleDelete(room.id); }}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={openDialog} onClose={() => { setOpenDialog(false); }} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingRoom ? 'Edit Room' : 'Add New Room'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Room Number"
            value={formData.room_number}
            onChange={(e) => { setFormData({ ...formData, room_number: e.target.value }); }}
            margin="normal"
            required
            placeholder="e.g., A101, B205"
          />
          <TextField
            fullWidth
            label="Building"
            value={formData.building}
            onChange={(e) => { setFormData({ ...formData, building: e.target.value }); }}
            margin="normal"
            required
            placeholder="e.g., Engineering Block A"
          />
          <TextField
            fullWidth
            select
            label="Room Type"
            value={formData.room_type}
            onChange={(e) => { setFormData({ ...formData, room_type: e.target.value }); }}
            margin="normal"
            required
          >
            {roomTypes.map((type) => (
              <MenuItem key={type.value} value={type.value}>
                {type.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth
            select
            label="Room Category"
            value={formData.room_category}
            onChange={(e) => { setFormData({ ...formData, room_category: e.target.value }); }}
            margin="normal"
          >
            {roomCategories.map((cat) => (
              <MenuItem key={cat.value} value={cat.value}>
                {cat.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth
            label="Dept. Affinity (Optional)"
            value={formData.department_affinity}
            onChange={(e) => { setFormData({ ...formData, department_affinity: e.target.value }); }}
            margin="normal"
            placeholder="e.g., AEN (Leave empty for general)"
          />
          <TextField
            fullWidth
            label="Capacity"
            type="number"
            value={formData.capacity}
            onChange={(e) => { setFormData({ ...formData, capacity: parseInt(e.target.value) }); }}
            margin="normal"
            required
            inputProps={{ min: 1, max: 500 }}
          />
          <TextField
            fullWidth
            label="Equipment"
            value={formData.equipment}
            onChange={(e) => { setFormData({ ...formData, equipment: e.target.value }); }}
            margin="normal"
            placeholder="Comma separated: Projector, Whiteboard, AC"
            helperText="Separate multiple items with commas"
            multiline
            rows={2}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={() => { void handleSubmit(); }} variant="contained">
            {editingRoom ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Upload Dialog */}
      <Dialog open={openBulkDialog} onClose={() => { setOpenBulkDialog(false); }} maxWidth="sm" fullWidth>
        <DialogTitle>Bulk Upload Rooms</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Upload a CSV or Excel file with the following columns:
            <br />
            <code>name, capacity, building, furniture_type, equipment, availability, priority</code>
          </Typography>
          <input
            accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
            style={{ display: 'none' }}
            id="bulk-upload-file"
            type="file"
            onChange={(e) => {
              const files = e.target.files;
              if (files && files.length > 0) {
                setBulkFile(files[0]);
              }
            }}
          />
          <label htmlFor="bulk-upload-file">
            <Button variant="outlined" component="span" fullWidth>
              {bulkFile ? bulkFile.name : 'Select File'}
            </Button>
          </label>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setOpenBulkDialog(false); }}>Cancel</Button>
          <Button
            onClick={() => { void handleBulkUpload(); }}
            variant="contained"
            disabled={!bulkFile}
          >
            Upload
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RoomsPage;
