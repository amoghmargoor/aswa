# Task 9.7.2: Template Library UI

## Objective

Implement the template library UI for browsing, searching, and instantiating agent templates with a user-friendly interface.

## Prerequisites

- Task 9.7.1 completed (Agent Templates)
- React/TypeScript UI framework
- Template API endpoints

## Implementation

### Step 1: Template Types and API Client

```typescript
// src/features/templates/types.ts
export type TemplateCategory =
  | 'productivity'
  | 'communication'
  | 'support'
  | 'sales'
  | 'hr'
  | 'it'
  | 'finance'
  | 'operations'
  | 'custom';

export type TemplateVisibility = 'public' | 'private' | 'shared';

export interface ConfigurableField {
  path: string;
  label: string;
  description?: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'multi-select';
  required: boolean;
  default?: unknown;
  options?: Array<{ value: string; label: string }>;
  validation?: Record<string, unknown>;
}

export interface AgentTemplate {
  id: string;
  name: string;
  slug: string;
  displayName: string;
  description: string | null;
  longDescription?: string | null;
  category: TemplateCategory;
  version: string;
  visibility: TemplateVisibility;
  tags: string[];
  icon: string | null;
  color: string | null;
  usageCount: number;
  rating: number | null;
  ratingCount?: number;
  published: boolean;
  featured: boolean;
  createdAt: string;
  requiredIntegrations: string[];
  requiredPermissions?: string[];
  definition?: Record<string, unknown>;
  defaultConfig?: Record<string, unknown>;
  configurableFields?: ConfigurableField[];
  placeholders?: Record<string, string>;
}

export interface TemplateListResponse {
  templates: AgentTemplate[];
  total: number;
  limit: number;
  offset: number;
}

export interface InstantiateTemplateRequest {
  templateId?: string;
  templateSlug?: string;
  agentName: string;
  configuration: Record<string, unknown>;
  deploy?: boolean;
}

export interface InstantiateTemplateResponse {
  agentId: string;
  agentName: string;
  templateId: string;
  templateName: string;
}
```

```typescript
// src/features/templates/api.ts
import { api } from '@/lib/api';
import type {
  AgentTemplate,
  TemplateListResponse,
  TemplateCategory,
  InstantiateTemplateRequest,
  InstantiateTemplateResponse,
} from './types';

export const templatesApi = {
  list: async (params?: {
    category?: TemplateCategory;
    search?: string;
    featured?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<TemplateListResponse> => {
    const response = await api.get<TemplateListResponse>('/templates', { params });
    return response.data;
  },

  listByCategory: async (): Promise<Record<string, AgentTemplate[]>> => {
    const response = await api.get<Record<string, AgentTemplate[]>>('/templates/categories');
    return response.data;
  },

  getById: async (id: string): Promise<AgentTemplate> => {
    const response = await api.get<AgentTemplate>(`/templates/${id}`);
    return response.data;
  },

  getBySlug: async (slug: string): Promise<AgentTemplate> => {
    const response = await api.get<AgentTemplate>(`/templates/slug/${slug}`);
    return response.data;
  },

  instantiate: async (request: InstantiateTemplateRequest): Promise<InstantiateTemplateResponse> => {
    const response = await api.post<InstantiateTemplateResponse>('/templates/instantiate', request);
    return response.data;
  },

  rate: async (id: string, rating: number): Promise<void> => {
    await api.post(`/templates/${id}/rate`, null, { params: { rating } });
  },

  // My templates
  listMine: async (includeDrafts?: boolean): Promise<TemplateListResponse> => {
    const response = await api.get<TemplateListResponse>('/templates/mine', {
      params: { include_drafts: includeDrafts },
    });
    return response.data;
  },

  create: async (template: Partial<AgentTemplate>): Promise<AgentTemplate> => {
    const response = await api.post<AgentTemplate>('/templates', template);
    return response.data;
  },

  update: async (id: string, updates: Partial<AgentTemplate>): Promise<AgentTemplate> => {
    const response = await api.put<AgentTemplate>(`/templates/${id}`, updates);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/templates/${id}`);
  },

  createFromAgent: async (agentId: string, name: string, description?: string): Promise<AgentTemplate> => {
    const response = await api.post<AgentTemplate>(`/templates/from-agent/${agentId}`, null, {
      params: { name, description },
    });
    return response.data;
  },
};
```

### Step 2: Template Library Page

```tsx
// src/features/templates/components/TemplateLibrary.tsx
import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templatesApi } from '../api';
import type { TemplateCategory, AgentTemplate } from '../types';
import { TemplateGrid } from './TemplateGrid';
import { TemplateDetailModal } from './TemplateDetailModal';
import { CategoryFilter } from './CategoryFilter';
import { SearchBar } from './SearchBar';

const CATEGORY_INFO: Record<TemplateCategory, { label: string; icon: string; color: string }> = {
  productivity: { label: 'Productivity', icon: '📊', color: 'bg-blue-500' },
  communication: { label: 'Communication', icon: '💬', color: 'bg-green-500' },
  support: { label: 'Support', icon: '🎧', color: 'bg-purple-500' },
  sales: { label: 'Sales', icon: '💰', color: 'bg-yellow-500' },
  hr: { label: 'HR', icon: '👥', color: 'bg-pink-500' },
  it: { label: 'IT', icon: '💻', color: 'bg-indigo-500' },
  finance: { label: 'Finance', icon: '📈', color: 'bg-emerald-500' },
  operations: { label: 'Operations', icon: '⚙️', color: 'bg-orange-500' },
  custom: { label: 'Custom', icon: '🔧', color: 'bg-gray-500' },
};

export const TemplateLibrary: React.FC = () => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<TemplateCategory | 'all'>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const { data, isLoading, error } = useQuery({
    queryKey: ['templates', selectedCategory, search],
    queryFn: () =>
      templatesApi.list({
        category: selectedCategory !== 'all' ? selectedCategory : undefined,
        search: search || undefined,
        limit: 100,
      }),
  });

  const { data: featuredData } = useQuery({
    queryKey: ['templates', 'featured'],
    queryFn: () => templatesApi.list({ featured: true, limit: 6 }),
    enabled: selectedCategory === 'all' && !search,
  });

  const groupedTemplates = useMemo(() => {
    if (!data?.templates) return {};

    return data.templates.reduce((acc, template) => {
      const category = template.category;
      if (!acc[category]) acc[category] = [];
      acc[category].push(template);
      return acc;
    }, {} as Record<string, AgentTemplate[]>);
  }, [data?.templates]);

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load templates. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Agent Templates</h1>
        <p className="mt-2 text-gray-600">
          Browse pre-built agent configurations or create your own
        </p>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-8">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search templates..."
          className="flex-1"
        />
        <div className="flex gap-2">
          <CategoryFilter
            categories={Object.entries(CATEGORY_INFO).map(([key, info]) => ({
              value: key as TemplateCategory,
              ...info,
            }))}
            selected={selectedCategory}
            onChange={setSelectedCategory}
          />
          <ViewToggle mode={viewMode} onChange={setViewMode} />
        </div>
      </div>

      {isLoading ? (
        <TemplateGridSkeleton />
      ) : (
        <>
          {/* Featured Section */}
          {featuredData?.templates && featuredData.templates.length > 0 && selectedCategory === 'all' && !search && (
            <section className="mb-12">
              <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <span className="text-yellow-500">⭐</span> Featured Templates
              </h2>
              <TemplateGrid
                templates={featuredData.templates}
                onSelect={setSelectedTemplate}
                featured
              />
            </section>
          )}

          {/* Category Sections or Flat List */}
          {selectedCategory === 'all' && !search ? (
            Object.entries(groupedTemplates).map(([category, templates]) => (
              <section key={category} className="mb-10">
                <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <span>{CATEGORY_INFO[category as TemplateCategory]?.icon}</span>
                  {CATEGORY_INFO[category as TemplateCategory]?.label || category}
                  <span className="text-sm font-normal text-gray-500">
                    ({templates.length})
                  </span>
                </h2>
                <TemplateGrid
                  templates={templates.slice(0, 4)}
                  onSelect={setSelectedTemplate}
                />
                {templates.length > 4 && (
                  <button
                    onClick={() => setSelectedCategory(category as TemplateCategory)}
                    className="mt-4 text-blue-600 hover:text-blue-700 text-sm font-medium"
                  >
                    View all {templates.length} templates →
                  </button>
                )}
              </section>
            ))
          ) : (
            <TemplateGrid
              templates={data?.templates || []}
              onSelect={setSelectedTemplate}
              viewMode={viewMode}
            />
          )}

          {/* Empty State */}
          {data?.templates.length === 0 && (
            <EmptyState
              search={search}
              category={selectedCategory}
              onClear={() => {
                setSearch('');
                setSelectedCategory('all');
              }}
            />
          )}
        </>
      )}

      {/* Template Detail Modal */}
      {selectedTemplate && (
        <TemplateDetailModal
          template={selectedTemplate}
          onClose={() => setSelectedTemplate(null)}
        />
      )}
    </div>
  );
};

const ViewToggle: React.FC<{
  mode: 'grid' | 'list';
  onChange: (mode: 'grid' | 'list') => void;
}> = ({ mode, onChange }) => (
  <div className="flex rounded-md border border-gray-300 overflow-hidden">
    <button
      onClick={() => onChange('grid')}
      className={`px-3 py-2 ${mode === 'grid' ? 'bg-gray-100' : 'bg-white'}`}
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    </button>
    <button
      onClick={() => onChange('list')}
      className={`px-3 py-2 ${mode === 'list' ? 'bg-gray-100' : 'bg-white'}`}
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
  </div>
);

const EmptyState: React.FC<{
  search: string;
  category: string;
  onClear: () => void;
}> = ({ search, category, onClear }) => (
  <div className="text-center py-16 bg-gray-50 rounded-lg">
    <svg
      className="mx-auto h-12 w-12 text-gray-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
    <h3 className="mt-4 text-lg font-medium text-gray-900">No templates found</h3>
    <p className="mt-2 text-gray-500">
      {search
        ? `No templates match "${search}"`
        : `No templates in this category`}
    </p>
    <button
      onClick={onClear}
      className="mt-4 text-blue-600 hover:text-blue-700"
    >
      Clear filters
    </button>
  </div>
);

const TemplateGridSkeleton: React.FC = () => (
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
    {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
      <div key={i} className="animate-pulse">
        <div className="bg-gray-200 rounded-lg h-48" />
      </div>
    ))}
  </div>
);
```

### Step 3: Template Grid and Cards

```tsx
// src/features/templates/components/TemplateGrid.tsx
import React from 'react';
import clsx from 'clsx';
import type { AgentTemplate } from '../types';
import { TemplateCard } from './TemplateCard';

interface TemplateGridProps {
  templates: AgentTemplate[];
  onSelect: (template: AgentTemplate) => void;
  viewMode?: 'grid' | 'list';
  featured?: boolean;
}

export const TemplateGrid: React.FC<TemplateGridProps> = ({
  templates,
  onSelect,
  viewMode = 'grid',
  featured = false,
}) => {
  if (viewMode === 'list') {
    return (
      <div className="space-y-3">
        {templates.map((template) => (
          <TemplateListItem
            key={template.id}
            template={template}
            onClick={() => onSelect(template)}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'grid gap-6',
        featured
          ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
          : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
      )}
    >
      {templates.map((template) => (
        <TemplateCard
          key={template.id}
          template={template}
          onClick={() => onSelect(template)}
          featured={featured}
        />
      ))}
    </div>
  );
};

const TemplateListItem: React.FC<{
  template: AgentTemplate;
  onClick: () => void;
}> = ({ template, onClick }) => (
  <div
    onClick={onClick}
    className="flex items-center gap-4 p-4 bg-white border rounded-lg hover:shadow-md cursor-pointer transition-shadow"
  >
    <TemplateIcon template={template} size="md" />
    <div className="flex-1 min-w-0">
      <h3 className="text-sm font-medium text-gray-900 truncate">
        {template.displayName}
      </h3>
      <p className="text-sm text-gray-500 truncate">{template.description}</p>
    </div>
    <div className="flex items-center gap-4 text-sm text-gray-500">
      <span>{template.usageCount} uses</span>
      {template.rating && (
        <span className="flex items-center gap-1">
          <span className="text-yellow-500">★</span>
          {template.rating}
        </span>
      )}
    </div>
    <svg
      className="w-5 h-5 text-gray-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  </div>
);
```

```tsx
// src/features/templates/components/TemplateCard.tsx
import React from 'react';
import clsx from 'clsx';
import type { AgentTemplate } from '../types';

interface TemplateCardProps {
  template: AgentTemplate;
  onClick: () => void;
  featured?: boolean;
}

const ICON_MAP: Record<string, string> = {
  mail: '📧',
  headphones: '🎧',
  calendar: '📅',
  'message-circle': '💬',
  default: '🤖',
};

export const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  onClick,
  featured = false,
}) => {
  const icon = ICON_MAP[template.icon || 'default'] || ICON_MAP.default;

  return (
    <div
      onClick={onClick}
      className={clsx(
        'relative bg-white border rounded-xl overflow-hidden cursor-pointer transition-all',
        'hover:shadow-lg hover:border-blue-300',
        featured && 'ring-2 ring-yellow-400'
      )}
    >
      {/* Header with gradient */}
      <div
        className="h-24 flex items-center justify-center"
        style={{
          background: template.color
            ? `linear-gradient(135deg, ${template.color}, ${adjustColor(template.color, -20)})`
            : 'linear-gradient(135deg, #3B82F6, #1D4ED8)',
        }}
      >
        <span className="text-4xl">{icon}</span>
        {template.featured && (
          <span className="absolute top-2 right-2 bg-yellow-400 text-yellow-900 text-xs font-bold px-2 py-1 rounded">
            Featured
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="text-lg font-semibold text-gray-900 truncate">
          {template.displayName}
        </h3>
        <p className="mt-1 text-sm text-gray-500 line-clamp-2 h-10">
          {template.description}
        </p>

        {/* Tags */}
        <div className="mt-3 flex flex-wrap gap-1">
          {template.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
            >
              {tag}
            </span>
          ))}
          {template.tags.length > 3 && (
            <span className="text-xs text-gray-500">
              +{template.tags.length - 3}
            </span>
          )}
        </div>

        {/* Footer */}
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="flex items-center gap-3 text-gray-500">
            <span>{template.usageCount.toLocaleString()} uses</span>
            {template.rating && (
              <span className="flex items-center gap-1">
                <span className="text-yellow-500">★</span>
                {template.rating.toFixed(1)}
              </span>
            )}
          </div>
          <span className="text-xs text-gray-400 capitalize">
            {template.category}
          </span>
        </div>

        {/* Required integrations */}
        {template.requiredIntegrations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-500">Requires: </span>
            {template.requiredIntegrations.map((integration, i) => (
              <span key={integration} className="text-xs text-gray-600">
                {integration}
                {i < template.requiredIntegrations.length - 1 && ', '}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Helper to adjust color brightness
function adjustColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16);
  const r = Math.min(255, Math.max(0, (num >> 16) + amount));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
  const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
  return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}
```

### Step 4: Template Detail Modal

```tsx
// src/features/templates/components/TemplateDetailModal.tsx
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { templatesApi } from '../api';
import type { AgentTemplate, ConfigurableField } from '../types';
import { ConfigurationForm } from './ConfigurationForm';

interface TemplateDetailModalProps {
  template: AgentTemplate;
  onClose: () => void;
}

export const TemplateDetailModal: React.FC<TemplateDetailModalProps> = ({
  template: initialTemplate,
  onClose,
}) => {
  const [step, setStep] = useState<'details' | 'configure'>('details');
  const [agentName, setAgentName] = useState('');
  const [configuration, setConfiguration] = useState<Record<string, unknown>>({});
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch full template details
  const { data: template } = useQuery({
    queryKey: ['template', initialTemplate.id],
    queryFn: () => templatesApi.getById(initialTemplate.id),
    initialData: initialTemplate,
  });

  const instantiateMutation = useMutation({
    mutationFn: () =>
      templatesApi.instantiate({
        templateId: template.id,
        agentName,
        configuration,
        deploy: false,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      onClose();
      navigate(`/agents/${data.agentId}`);
    },
  });

  const handleStartConfiguration = () => {
    // Set default values from template
    const defaults: Record<string, unknown> = {};
    template.configurableFields?.forEach((field) => {
      if (field.default !== undefined) {
        defaults[field.path] = field.default;
      }
    });
    // Apply template defaults
    if (template.defaultConfig) {
      Object.assign(defaults, template.defaultConfig);
    }
    setConfiguration(defaults);
    setStep('configure');
  };

  const handleCreate = () => {
    if (!agentName.trim()) return;
    instantiateMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
          {step === 'details' ? (
            <TemplateDetails
              template={template}
              onClose={onClose}
              onUseTemplate={handleStartConfiguration}
            />
          ) : (
            <TemplateConfiguration
              template={template}
              agentName={agentName}
              onAgentNameChange={setAgentName}
              configuration={configuration}
              onConfigurationChange={setConfiguration}
              onBack={() => setStep('details')}
              onCancel={onClose}
              onCreate={handleCreate}
              isCreating={instantiateMutation.isPending}
              error={instantiateMutation.error?.message}
            />
          )}
        </div>
      </div>
    </div>
  );
};

interface TemplateDetailsProps {
  template: AgentTemplate;
  onClose: () => void;
  onUseTemplate: () => void;
}

const TemplateDetails: React.FC<TemplateDetailsProps> = ({
  template,
  onClose,
  onUseTemplate,
}) => (
  <>
    {/* Header with gradient */}
    <div
      className="h-32 flex items-center justify-center relative"
      style={{
        background: template.color
          ? `linear-gradient(135deg, ${template.color}, ${adjustColor(template.color, -20)})`
          : 'linear-gradient(135deg, #3B82F6, #1D4ED8)',
      }}
    >
      <span className="text-6xl">{getIcon(template.icon)}</span>
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-white/80 hover:text-white"
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    {/* Content */}
    <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{template.displayName}</h2>
          <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
            <span className="capitalize">{template.category}</span>
            <span>•</span>
            <span>v{template.version}</span>
            <span>•</span>
            <span>{template.usageCount.toLocaleString()} uses</span>
            {template.rating && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <span className="text-yellow-500">★</span>
                  {template.rating.toFixed(1)}
                </span>
              </>
            )}
          </div>
        </div>
        {template.featured && (
          <span className="bg-yellow-100 text-yellow-800 text-xs font-bold px-2 py-1 rounded">
            Featured
          </span>
        )}
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-6">
        {template.tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Description */}
      <div className="prose prose-sm max-w-none mb-6">
        {template.longDescription ? (
          <ReactMarkdown>{template.longDescription}</ReactMarkdown>
        ) : (
          <p className="text-gray-600">{template.description}</p>
        )}
      </div>

      {/* Required Integrations */}
      {template.requiredIntegrations.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-900 mb-2">
            Required Integrations
          </h3>
          <div className="flex flex-wrap gap-2">
            {template.requiredIntegrations.map((integration) => (
              <span
                key={integration}
                className="inline-flex items-center px-3 py-1 rounded-md text-sm bg-gray-100 text-gray-700"
              >
                {getIntegrationIcon(integration)} {integration}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Configurable Fields Preview */}
      {template.configurableFields && template.configurableFields.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-900 mb-2">
            Customizable Options
          </h3>
          <ul className="text-sm text-gray-600 space-y-1">
            {template.configurableFields.slice(0, 5).map((field) => (
              <li key={field.path} className="flex items-center gap-2">
                <span className="text-gray-400">•</span>
                {field.label}
                {field.required && <span className="text-red-500">*</span>}
              </li>
            ))}
            {template.configurableFields.length > 5 && (
              <li className="text-gray-400">
                +{template.configurableFields.length - 5} more options
              </li>
            )}
          </ul>
        </div>
      )}
    </div>

    {/* Footer */}
    <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
      <button
        onClick={onClose}
        className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
      >
        Cancel
      </button>
      <button
        onClick={onUseTemplate}
        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
      >
        Use This Template
      </button>
    </div>
  </>
);

interface TemplateConfigurationProps {
  template: AgentTemplate;
  agentName: string;
  onAgentNameChange: (name: string) => void;
  configuration: Record<string, unknown>;
  onConfigurationChange: (config: Record<string, unknown>) => void;
  onBack: () => void;
  onCancel: () => void;
  onCreate: () => void;
  isCreating: boolean;
  error?: string;
}

const TemplateConfiguration: React.FC<TemplateConfigurationProps> = ({
  template,
  agentName,
  onAgentNameChange,
  configuration,
  onConfigurationChange,
  onBack,
  onCancel,
  onCreate,
  isCreating,
  error,
}) => (
  <>
    {/* Header */}
    <div className="px-6 py-4 border-b border-gray-200">
      <h2 className="text-lg font-semibold text-gray-900">
        Configure Your Agent
      </h2>
      <p className="text-sm text-gray-500">
        Customize {template.displayName} to fit your needs
      </p>
    </div>

    {/* Content */}
    <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Agent Name */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Agent Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={agentName}
          onChange={(e) => onAgentNameChange(e.target.value)}
          placeholder="My Email Agent"
          className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <p className="mt-1 text-xs text-gray-500">
          Give your agent a descriptive name
        </p>
      </div>

      {/* Configuration Form */}
      {template.configurableFields && template.configurableFields.length > 0 && (
        <ConfigurationForm
          fields={template.configurableFields}
          values={configuration}
          onChange={onConfigurationChange}
        />
      )}
    </div>

    {/* Footer */}
    <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
      <button
        onClick={onBack}
        className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        ← Back to Details
      </button>
      <div className="flex gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
        >
          Cancel
        </button>
        <button
          onClick={onCreate}
          disabled={!agentName.trim() || isCreating}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isCreating ? 'Creating...' : 'Create Agent'}
        </button>
      </div>
    </div>
  </>
);

// Helper functions
function getIcon(iconName: string | null): string {
  const icons: Record<string, string> = {
    mail: '📧',
    headphones: '🎧',
    calendar: '📅',
    'message-circle': '💬',
  };
  return icons[iconName || ''] || '🤖';
}

function getIntegrationIcon(integration: string): string {
  const icons: Record<string, string> = {
    slack: '💬',
    email: '📧',
    jira: '📋',
    github: '🐙',
    linear: '📊',
  };
  return icons[integration.toLowerCase()] || '🔌';
}

function adjustColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16);
  const r = Math.min(255, Math.max(0, (num >> 16) + amount));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
  const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
  return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}
```

### Step 5: Configuration Form

```tsx
// src/features/templates/components/ConfigurationForm.tsx
import React from 'react';
import type { ConfigurableField } from '../types';

interface ConfigurationFormProps {
  fields: ConfigurableField[];
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
}

export const ConfigurationForm: React.FC<ConfigurationFormProps> = ({
  fields,
  values,
  onChange,
}) => {
  const updateValue = (path: string, value: unknown) => {
    onChange({ ...values, [path]: value });
  };

  // Group fields by category (extracted from path)
  const groupedFields = fields.reduce((acc, field) => {
    const category = field.path.split('.')[0] || 'General';
    if (!acc[category]) acc[category] = [];
    acc[category].push(field);
    return acc;
  }, {} as Record<string, ConfigurableField[]>);

  return (
    <div className="space-y-6">
      {Object.entries(groupedFields).map(([category, categoryFields]) => (
        <div key={category}>
          <h3 className="text-sm font-medium text-gray-900 mb-3 capitalize">
            {formatCategoryName(category)} Settings
          </h3>
          <div className="space-y-4 bg-gray-50 rounded-lg p-4">
            {categoryFields.map((field) => (
              <FieldInput
                key={field.path}
                field={field}
                value={values[field.path]}
                onChange={(value) => updateValue(field.path, value)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

interface FieldInputProps {
  field: ConfigurableField;
  value: unknown;
  onChange: (value: unknown) => void;
}

const FieldInput: React.FC<FieldInputProps> = ({ field, value, onChange }) => {
  const inputId = `field-${field.path.replace(/\./g, '-')}`;

  const renderInput = () => {
    switch (field.type) {
      case 'boolean':
        return (
          <label className="flex items-center gap-2">
            <input
              id={inputId}
              type="checkbox"
              checked={Boolean(value)}
              onChange={(e) => onChange(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">{field.label}</span>
          </label>
        );

      case 'number':
        return (
          <input
            id={inputId}
            type="number"
            value={value as number ?? ''}
            onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          />
        );

      case 'select':
        return (
          <select
            id={inputId}
            value={value as string ?? ''}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select...</option>
            {field.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'multi-select':
        return (
          <div className="space-y-2">
            {field.options?.map((option) => {
              const selectedValues = (value as string[]) || [];
              const isChecked = selectedValues.includes(option.value);
              return (
                <label key={option.value} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={(e) => {
                      if (e.target.checked) {
                        onChange([...selectedValues, option.value]);
                      } else {
                        onChange(selectedValues.filter((v) => v !== option.value));
                      }
                    }}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{option.label}</span>
                </label>
              );
            })}
          </div>
        );

      case 'string':
      default:
        return (
          <input
            id={inputId}
            type="text"
            value={value as string ?? ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.default as string}
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          />
        );
    }
  };

  if (field.type === 'boolean') {
    return (
      <div>
        {renderInput()}
        {field.description && (
          <p className="mt-1 text-xs text-gray-500 ml-6">{field.description}</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {renderInput()}
      {field.description && (
        <p className="mt-1 text-xs text-gray-500">{field.description}</p>
      )}
    </div>
  );
};

function formatCategoryName(category: string): string {
  return category
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}
```

### Step 6: Search and Filter Components

```tsx
// src/features/templates/components/SearchBar.tsx
import React, { useState, useEffect } from 'react';
import { useDebounce } from '@/hooks/useDebounce';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = 'Search...',
  className = '',
}) => {
  const [localValue, setLocalValue] = useState(value);
  const debouncedValue = useDebounce(localValue, 300);

  useEffect(() => {
    onChange(debouncedValue);
  }, [debouncedValue, onChange]);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  return (
    <div className={`relative ${className}`}>
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <svg
          className="h-5 w-5 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={placeholder}
        className="block w-full pl-10 pr-10 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
      />
      {localValue && (
        <button
          onClick={() => {
            setLocalValue('');
            onChange('');
          }}
          className="absolute inset-y-0 right-0 pr-3 flex items-center"
        >
          <svg
            className="h-5 w-5 text-gray-400 hover:text-gray-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
};
```

```tsx
// src/features/templates/components/CategoryFilter.tsx
import React, { useState, useRef, useEffect } from 'react';
import type { TemplateCategory } from '../types';

interface Category {
  value: TemplateCategory;
  label: string;
  icon: string;
  color: string;
}

interface CategoryFilterProps {
  categories: Category[];
  selected: TemplateCategory | 'all';
  onChange: (category: TemplateCategory | 'all') => void;
}

export const CategoryFilter: React.FC<CategoryFilterProps> = ({
  categories,
  selected,
  onChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedCategory = categories.find((c) => c.value === selected);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-md bg-white hover:bg-gray-50 text-sm"
      >
        {selected === 'all' ? (
          <>
            <span>📁</span>
            <span>All Categories</span>
          </>
        ) : (
          <>
            <span>{selectedCategory?.icon}</span>
            <span>{selectedCategory?.label}</span>
          </>
        )}
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-gray-200 z-10">
          <div className="py-1">
            <button
              onClick={() => {
                onChange('all');
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-2 px-4 py-2 text-sm text-left hover:bg-gray-100 ${
                selected === 'all' ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
              }`}
            >
              <span>📁</span>
              <span>All Categories</span>
            </button>
            <div className="border-t border-gray-100 my-1" />
            {categories.map((category) => (
              <button
                key={category.value}
                onClick={() => {
                  onChange(category.value);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-4 py-2 text-sm text-left hover:bg-gray-100 ${
                  selected === category.value ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                }`}
              >
                <span>{category.icon}</span>
                <span>{category.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
```

## Test Cases

```typescript
// src/features/templates/__tests__/TemplateLibrary.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { TemplateLibrary } from '../components/TemplateLibrary';
import { templatesApi } from '../api';

jest.mock('../api');

const mockTemplates = [
  {
    id: '1',
    name: 'email-summarizer',
    slug: 'email-summarizer',
    displayName: 'Email Summarizer',
    description: 'Summarize incoming emails',
    category: 'productivity',
    version: '1.0.0',
    visibility: 'public',
    tags: ['email', 'productivity'],
    icon: 'mail',
    color: '#3B82F6',
    usageCount: 150,
    rating: 4.5,
    published: true,
    featured: true,
    createdAt: new Date().toISOString(),
    requiredIntegrations: ['email', 'slack'],
  },
  {
    id: '2',
    name: 'support-router',
    slug: 'support-router',
    displayName: 'Support Ticket Router',
    description: 'Route support tickets automatically',
    category: 'support',
    version: '1.0.0',
    visibility: 'public',
    tags: ['support', 'tickets'],
    icon: 'headphones',
    color: '#10B981',
    usageCount: 75,
    rating: 4.2,
    published: true,
    featured: false,
    createdAt: new Date().toISOString(),
    requiredIntegrations: ['zendesk'],
  },
];

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('TemplateLibrary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders template library with templates', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: mockTemplates,
      total: 2,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
      expect(screen.getByText('Support Ticket Router')).toBeInTheDocument();
    });
  });

  it('filters templates by search', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: mockTemplates,
      total: 2,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search templates...');
    fireEvent.change(searchInput, { target: { value: 'email' } });

    await waitFor(() => {
      expect(templatesApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'email' })
      );
    });
  });

  it('filters templates by category', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: mockTemplates,
      total: 2,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
    });

    // Click category filter
    fireEvent.click(screen.getByText('All Categories'));
    fireEvent.click(screen.getByText('Support'));

    await waitFor(() => {
      expect(templatesApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'support' })
      );
    });
  });

  it('shows empty state when no templates match', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [],
      total: 0,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No templates found')).toBeInTheDocument();
    });
  });

  it('opens template detail modal on click', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: mockTemplates,
      total: 2,
    });
    (templatesApi.getById as jest.Mock).mockResolvedValue(mockTemplates[0]);

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Email Summarizer'));

    await waitFor(() => {
      expect(screen.getByText('Use This Template')).toBeInTheDocument();
    });
  });
});

describe('TemplateCard', () => {
  it('displays template information correctly', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [mockTemplates[0]],
      total: 1,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
      expect(screen.getByText('150 uses')).toBeInTheDocument();
      expect(screen.getByText('4.5')).toBeInTheDocument();
      expect(screen.getByText('email')).toBeInTheDocument();
      expect(screen.getByText('productivity')).toBeInTheDocument();
    });
  });

  it('shows featured badge for featured templates', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [mockTemplates[0]],
      total: 1,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Featured')).toBeInTheDocument();
    });
  });

  it('displays required integrations', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [mockTemplates[0]],
      total: 1,
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Requires:/)).toBeInTheDocument();
      expect(screen.getByText(/email/)).toBeInTheDocument();
    });
  });
});

describe('TemplateDetailModal', () => {
  it('shows configuration step when using template', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [mockTemplates[0]],
      total: 1,
    });
    (templatesApi.getById as jest.Mock).mockResolvedValue({
      ...mockTemplates[0],
      configurableFields: [
        {
          path: 'trigger.config.filter',
          label: 'Email Filter',
          type: 'string',
          required: false,
          default: 'is:unread',
        },
      ],
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Email Summarizer')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Email Summarizer'));

    await waitFor(() => {
      expect(screen.getByText('Use This Template')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Use This Template'));

    await waitFor(() => {
      expect(screen.getByText('Configure Your Agent')).toBeInTheDocument();
      expect(screen.getByLabelText(/Agent Name/)).toBeInTheDocument();
    });
  });

  it('creates agent on form submission', async () => {
    (templatesApi.list as jest.Mock).mockResolvedValue({
      templates: [mockTemplates[0]],
      total: 1,
    });
    (templatesApi.getById as jest.Mock).mockResolvedValue(mockTemplates[0]);
    (templatesApi.instantiate as jest.Mock).mockResolvedValue({
      agentId: 'new-agent-id',
      agentName: 'My Agent',
      templateId: '1',
      templateName: 'email-summarizer',
    });

    render(<TemplateLibrary />, { wrapper: createWrapper() });

    await waitFor(() => {
      fireEvent.click(screen.getByText('Email Summarizer'));
    });

    await waitFor(() => {
      fireEvent.click(screen.getByText('Use This Template'));
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/Agent Name/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Agent Name/), {
      target: { value: 'My Email Agent' },
    });

    fireEvent.click(screen.getByText('Create Agent'));

    await waitFor(() => {
      expect(templatesApi.instantiate).toHaveBeenCalledWith({
        templateId: '1',
        agentName: 'My Email Agent',
        configuration: {},
        deploy: false,
      });
    });
  });
});
```

## Verification Steps

1. **Run component tests:**
   ```bash
   npm test -- --testPathPattern=templates
   ```

2. **Test template library:**
   - Navigate to /templates
   - Verify templates load and display correctly
   - Test search functionality
   - Test category filtering
   - Verify featured templates section

3. **Test template detail:**
   - Click on a template card
   - Verify modal displays full details
   - Check long description renders markdown
   - Verify required integrations display

4. **Test template instantiation:**
   - Click "Use This Template"
   - Fill in agent name
   - Configure customizable fields
   - Create agent and verify redirect

5. **Test responsive layout:**
   - Verify grid adjusts on different screen sizes
   - Test on mobile viewport

## Next Task

Proceed to `task-9.7.3-agent-sharing.md` for implementing agent sharing functionality.
