import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';
import * as AuthContext from '../contexts/AuthContext';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../contexts/AuthContext', () => ({
    useAuth: vi.fn(),
}));

const createAuthValue = (overrides: Partial<ReturnType<typeof AuthContext.useAuth>> = {}) => ({
    user: null,
    token: null,
    loading: false,
    login: vi.fn(),
    loginWithToken: vi.fn(),
    logout: vi.fn(),
    isCoordinator: false,
    isHOD: false,
    isAdmin: false,
    isSuperadmin: false,
    ...overrides,
});

describe('ProtectedRoute', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders loading spinner when loading is true', () => {
        vi.mocked(AuthContext.useAuth).mockReturnValue(createAuthValue({
            loading: true,
        }));

        render(
            <MemoryRouter>
                <ProtectedRoute>
                    <div data-testid="protected-content">Content</div>
                </ProtectedRoute>
            </MemoryRouter>
        );

        expect(screen.getByRole('progressbar')).toBeInTheDocument();
        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });

    it('redirects to /login when user is not authenticated', () => {
        vi.mocked(AuthContext.useAuth).mockReturnValue(createAuthValue());

        render(
            <MemoryRouter initialEntries={['/protected']}>
                <Routes>
                    <Route 
                        path="/protected" 
                        element={
                            <ProtectedRoute>
                                <div data-testid="protected-content">Content</div>
                            </ProtectedRoute>
                        } 
                    />
                    <Route path="/login" element={<div data-testid="login-page">Login Page</div>} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByTestId('login-page')).toBeInTheDocument();
        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });

    it('renders children when user is authenticated with correct role', () => {
        vi.mocked(AuthContext.useAuth).mockReturnValue(createAuthValue({
            user: { id: 1, email: 'test@unza.zm', role: 'admin', username: 'admin', full_name: 'Admin', is_active: true },
            token: 'mock-token',
            isAdmin: true,
        }));

        render(
            <MemoryRouter>
                <ProtectedRoute requiredRole="admin">
                    <div data-testid="protected-content">Content</div>
                </ProtectedRoute>
            </MemoryRouter>
        );

        expect(screen.getByTestId('protected-content')).toBeInTheDocument();
    });

    it('redirects to /dashboard when user lacks required role', () => {
        vi.mocked(AuthContext.useAuth).mockReturnValue(createAuthValue({
            user: { id: 1, email: 'test@unza.zm', role: 'lecturer', username: 'lecturer', full_name: 'Lecturer', is_active: true },
            token: 'mock-token',
        }));

        render(
            <MemoryRouter initialEntries={['/admin-only']}>
                <Routes>
                    <Route 
                        path="/admin-only" 
                        element={
                            <ProtectedRoute requiredRole="admin">
                                <div data-testid="admin-content">Admin Content</div>
                            </ProtectedRoute>
                        } 
                    />
                    <Route path="/dashboard" element={<div data-testid="dashboard-page">Dashboard Dashboard</div>} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
        expect(screen.queryByTestId('admin-content')).not.toBeInTheDocument();
    });
});
