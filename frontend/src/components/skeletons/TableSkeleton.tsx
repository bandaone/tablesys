import React from 'react';
import {
  Box,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

const TableSkeleton: React.FC<TableSkeletonProps> = ({ rows = 5, columns = 5 }) => {
  return (
    <TableContainer component={Paper} sx={{ mt: 3, mb: 3 }}>
      <Table>
        <TableHead>
          <TableRow>
            {[...Array(columns)].map((_, i) => (
              <TableCell key={`thead-${i}`}>
                <Skeleton variant="text" width="60%" height={32} />
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {[...Array(rows)].map((_, rowIndex) => (
            <TableRow key={`trow-${rowIndex}`}>
              {[...Array(columns)].map((_, colIndex) => (
                <TableCell key={`tcell-${rowIndex}-${colIndex}`}>
                  <Skeleton variant="text" width={colIndex === 0 ? "80%" : "60%"} height={24} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default TableSkeleton;
