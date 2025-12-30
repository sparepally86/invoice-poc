import React, { useState, useEffect } from 'react';
import { Loader, AlertCircle } from 'lucide-react';
import RuleCard from './RuleCard';

/**
 * Grid display component for all validation rules
 */
const RulesGrid = ({
  rules,
  loading,
  error,
  onEdit,
  onViewHistory,
  onDisable,
  onView,
  orgId,
  region
}) => {
  const [sortBy, setSortBy] = useState('category');
  const [filterCategory, setFilterCategory] = useState(null);
  const [sortedRules, setSortedRules] = useState([]);

  useEffect(() => {
    let filtered = [...rules];

    // Apply category filter
    if (filterCategory) {
      filtered = filtered.filter(r => r.rule_category === filterCategory);
    }

    // Apply sorting
    if (sortBy === 'category') {
      const categoryOrder = { 'STRUCTURAL': 0, 'FINANCIAL': 1, 'POLICY': 2, 'DUPLICATE': 3 };
      filtered.sort((a, b) => 
        (categoryOrder[a.rule_category] || 999) - (categoryOrder[b.rule_category] || 999)
      );
    } else if (sortBy === 'name') {
      filtered.sort((a, b) => a.rule_id.localeCompare(b.rule_id));
    } else if (sortBy === 'modified') {
      filtered.sort((a, b) => 
        new Date(b.updated_at || 0) - new Date(a.updated_at || 0)
      );
    }

    setSortedRules(filtered);
  }, [rules, sortBy, filterCategory]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader className="w-8 h-8 text-slate-400 animate-spin mb-2" />
        <p className="text-sm text-slate-500">Loading rules configuration...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        <AlertCircle className="w-5 h-5 flex-shrink-0" />
        <div>
          <p className="font-medium">Failed to load rules</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (rules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 bg-slate-50 border border-dashed border-slate-300 rounded-lg">
        <p className="text-sm text-slate-500 mb-2">No rules found for {orgId} / {region}</p>
        <p className="text-xs text-slate-400">Try selecting a different organization or region</p>
      </div>
    );
  }

  // Count by category
  const categoryCounts = {
    'STRUCTURAL': sortedRules.filter(r => r.rule_category === 'STRUCTURAL').length,
    'FINANCIAL': sortedRules.filter(r => r.rule_category === 'FINANCIAL').length,
    'POLICY': sortedRules.filter(r => r.rule_category === 'POLICY').length,
    'DUPLICATE': sortedRules.filter(r => r.rule_category === 'DUPLICATE').length
  };

  return (
    <div>
      {/* Controls */}
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        {/* Sort controls */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-700">Sort by:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white cursor-pointer"
          >
            <option value="category">Category</option>
            <option value="name">Rule ID</option>
            <option value="modified">Recently Modified</option>
          </select>
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-700">Filter:</label>
          <button
            onClick={() => setFilterCategory(null)}
            className={`px-3 py-1 text-sm rounded ${
              filterCategory === null
                ? 'bg-blue-500 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All ({rules.length})
          </button>
          {Object.entries(categoryCounts).map(([cat, count]) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(filterCategory === cat ? null : cat)}
              className={`px-3 py-1 text-sm rounded ${
                filterCategory === cat
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {cat} ({count})
            </button>
          ))}
        </div>
      </div>

      {/* Rules Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sortedRules.map(rule => (
          <RuleCard
            key={rule.rule_id}
            rule={rule}
            onEdit={onEdit}
            onViewHistory={onViewHistory}
            onDisable={onDisable}
            onView={onView}
          />
        ))}
      </div>

      {/* Summary footer */}
      <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-sm text-slate-600">
          Showing <strong>{sortedRules.length}</strong> of <strong>{rules.length}</strong> rules
          {filterCategory && ` (filtered by ${filterCategory})`}
        </p>
      </div>
    </div>
  );
};

export default RulesGrid;
