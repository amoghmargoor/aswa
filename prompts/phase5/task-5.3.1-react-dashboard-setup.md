# Task 5.3.1: Web Dashboard - React Setup

## Context

You are building the ASWA web dashboard at `/services/web-dashboard/`. This is a React/TypeScript application using Vite as the build tool.

## Objective

Create a React dashboard that:
1. Uses TypeScript and Vite
2. Implements routing with React Router
3. Uses TanStack Query for data fetching
4. Provides a component library foundation
5. Includes proper error boundaries

## Requirements

### 1. Create service structure

```
/services/web-dashboard/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── vite-env.d.ts
│   ├── components/
│   │   ├── ui/
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Input.tsx
│   │   │   └── index.ts
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── Layout.tsx
│   │   │   └── index.ts
│   │   └── common/
│   │       ├── ErrorBoundary.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── index.ts
│   ├── hooks/
│   │   ├── useQuery.ts
│   │   ├── useAuth.ts
│   │   └── index.ts
│   ├── services/
│   │   ├── api.ts
│   │   └── auth.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Query.tsx
│   │   ├── Insights.tsx
│   │   └── Settings.tsx
│   ├── types/
│   │   └── index.ts
│   └── utils/
│       └── index.ts
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

### 2. Create `/services/web-dashboard/package.json`
```json
{
  "name": "aswa-web-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "test": "vitest",
    "test:coverage": "vitest --coverage"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0",
    "date-fns": "^2.30.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.294.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.37",
    "@types/react-dom": "^18.2.15",
    "@typescript-eslint/eslint-plugin": "^6.10.0",
    "@typescript-eslint/parser": "^6.10.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.53.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.4",
    "postcss": "^8.4.31",
    "tailwindcss": "^3.3.5",
    "typescript": "^5.2.2",
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.1.0"
  }
}
```

### 3. Create `/services/web-dashboard/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 4. Create `/services/web-dashboard/vite.config.ts`
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### 5. Create `/services/web-dashboard/tailwind.config.js`
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
      },
    },
  },
  plugins: [],
};
```

### 6. Create `/services/web-dashboard/src/main.tsx`
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

### 7. Create `/services/web-dashboard/src/App.tsx`
```typescript
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout';
import { ErrorBoundary } from '@/components/common';
import Dashboard from '@/pages/Dashboard';
import Query from '@/pages/Query';
import Insights from '@/pages/Insights';
import Settings from '@/pages/Settings';
import { useAuth } from '@/hooks/useAuth';

function App() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/query" element={<Query />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  );
}

export default App;
```

### 8. Create `/services/web-dashboard/src/types/index.ts`
```typescript
export interface User {
  id: string;
  email: string;
  name: string;
  tenantId: string;
  role: 'admin' | 'user' | 'viewer';
}

export interface QueryRequest {
  query: string;
  documentIds?: string[];
  filters?: Record<string, unknown>;
}

export interface QueryResponse {
  id: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  processingTimeMs: number;
}

export interface Citation {
  index: number;
  documentId: string;
  documentName: string;
  pageNumber?: number;
  excerpt: string;
  relevanceScore: number;
}

export interface Insight {
  id: string;
  type: 'risk' | 'opportunity' | 'entity' | 'trend';
  title: string;
  description: string;
  confidence: number;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  documentId?: string;
  documentName?: string;
  createdAt: string;
}

export interface Document {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  insightCount: number;
  uploadedAt: string;
  processedAt?: string;
}

export interface DigestSummary {
  period: 'daily' | 'weekly';
  startDate: string;
  endDate: string;
  newDocuments: number;
  newInsights: number;
  topRisks: Insight[];
  topOpportunities: Insight[];
}

export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, unknown>;
}
```

### 9. Create `/services/web-dashboard/src/services/api.ts`
```typescript
import axios, { AxiosError, AxiosInstance } from 'axios';
import type { QueryRequest, QueryResponse, Insight, Document, DigestSummary } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Query endpoints
  async query(request: QueryRequest): Promise<QueryResponse> {
    const { data } = await this.client.post<QueryResponse>('/query', request);
    return data;
  }

  async getQueryHistory(limit = 20): Promise<QueryResponse[]> {
    const { data } = await this.client.get<QueryResponse[]>('/query/history', {
      params: { limit },
    });
    return data;
  }

  // Insight endpoints
  async getInsights(params?: {
    type?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Insight[]; total: number }> {
    const { data } = await this.client.get('/insights', { params });
    return data;
  }

  async getInsight(id: string): Promise<Insight> {
    const { data } = await this.client.get<Insight>(`/insights/${id}`);
    return data;
  }

  // Document endpoints
  async getDocuments(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Document[]; total: number }> {
    const { data } = await this.client.get('/documents', { params });
    return data;
  }

  async getDocument(id: string): Promise<Document> {
    const { data } = await this.client.get<Document>(`/documents/${id}`);
    return data;
  }

  async uploadDocument(file: File): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await this.client.post<Document>('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }

  // Digest endpoints
  async getDigest(period: 'daily' | 'weekly' = 'daily'): Promise<DigestSummary> {
    const { data } = await this.client.get<DigestSummary>('/digest', {
      params: { period },
    });
    return data;
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/health');
      return true;
    } catch {
      return false;
    }
  }
}

export const api = new ApiService();
```

### 10. Create `/services/web-dashboard/src/hooks/useAuth.ts`
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email: string, password: string) => {
        set({ isLoading: true });

        try {
          // Call auth API
          const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            throw new Error('Login failed');
          }

          const { user, token } = await response.json();

          localStorage.setItem('auth_token', token);

          set({
            user,
            token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('auth_token');
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });
      },

      setUser: (user: User) => {
        set({ user, isAuthenticated: true });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
);
```

### 11. Create `/services/web-dashboard/src/components/common/ErrorBoundary.tsx`
```typescript
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8">
            <div className="text-center">
              <div className="text-red-500 text-5xl mb-4">⚠️</div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Something went wrong
              </h1>
              <p className="text-gray-600 mb-6">
                An unexpected error occurred. Please try refreshing the page.
              </p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### 12. Create `/services/web-dashboard/src/components/common/LoadingSpinner.tsx`
```typescript
import { clsx } from 'clsx';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ size = 'md', className }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  };

  return (
    <div
      className={clsx(
        'animate-spin rounded-full border-b-2 border-primary-600',
        sizeClasses[size],
        className
      )}
    />
  );
}
```

### 13. Create `/services/web-dashboard/src/components/common/index.ts`
```typescript
export { ErrorBoundary } from './ErrorBoundary';
export { LoadingSpinner } from './LoadingSpinner';
```

### 14. Create `/services/web-dashboard/src/components/layout/Layout.tsx`
```typescript
import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div className="lg:pl-64">
        <Header />
        <main className="py-6 px-4 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
```

### 15. Create `/services/web-dashboard/src/components/layout/Sidebar.tsx`
```typescript
import { NavLink } from 'react-router-dom';
import { Home, Search, Lightbulb, Settings } from 'lucide-react';
import { clsx } from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Query', href: '/query', icon: Search },
  { name: 'Insights', href: '/insights', icon: Lightbulb },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  return (
    <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
      <div className="flex flex-col flex-grow bg-white border-r border-gray-200 pt-5 pb-4 overflow-y-auto">
        <div className="flex items-center flex-shrink-0 px-4">
          <span className="text-xl font-bold text-primary-600">ASWA</span>
        </div>
        <nav className="mt-8 flex-1 px-2 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  'group flex items-center px-3 py-2 text-sm font-medium rounded-lg',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-50'
                )
              }
            >
              <item.icon className="mr-3 h-5 w-5" />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
```

### 16. Create `/services/web-dashboard/src/components/layout/Header.tsx`
```typescript
import { useAuth } from '@/hooks/useAuth';
import { LogOut, User } from 'lucide-react';

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex-1" />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <User className="h-5 w-5" />
              <span>{user?.name || user?.email}</span>
            </div>
            <button
              onClick={logout}
              className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
              title="Logout"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
```

### 17. Create `/services/web-dashboard/src/components/layout/index.ts`
```typescript
export { Layout } from './Layout';
export { Sidebar } from './Sidebar';
export { Header } from './Header';
```

## Test Requirements

### Create `/services/web-dashboard/src/test/setup.ts`
```typescript
import '@testing-library/jest-dom';
```

### Create `/services/web-dashboard/src/components/common/ErrorBoundary.test.tsx`
```typescript
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

const ThrowError = () => {
  throw new Error('Test error');
};

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for cleaner test output
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>Test content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders error UI when error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });
});
```

## Verification

1. Install dependencies: `cd /services/web-dashboard && npm install`
2. Run dev server: `npm run dev`
3. Run tests: `npm test`
4. Build: `npm run build`
