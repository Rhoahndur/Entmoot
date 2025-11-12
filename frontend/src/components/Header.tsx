/**
 * Header component - Reusable navigation header for all pages
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import EntmootLogo from '../assets/entmoot-logo.svg';

interface HeaderProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, actions }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <header className="bg-white shadow-sm">
      <div className="max-w-full px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Left side - Logo and navigation */}
          <div className="flex items-center space-x-8">
            {/* Logo/Title */}
            <div
              onClick={() => navigate('/')}
              className="cursor-pointer hover:opacity-80 transition-opacity flex items-center space-x-3"
            >
              <img src={EntmootLogo} alt="Entmoot" className="w-10 h-10" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Entmoot</h1>
                {subtitle && <p className="mt-1 text-sm text-gray-600">{subtitle}</p>}
              </div>
            </div>

            {/* Navigation Links */}
            <nav className="hidden md:flex space-x-1">
              <button
                onClick={() => navigate('/')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/') || isActive('/upload')
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                New Project
              </button>
              <button
                onClick={() => navigate('/projects')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/projects')
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Projects
              </button>
            </nav>
          </div>

          {/* Right side - Title and actions */}
          <div className="flex items-center space-x-4">
            {title && (
              <div className="hidden sm:block text-right">
                <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
              </div>
            )}
            {actions && <div className="flex items-center space-x-3">{actions}</div>}
          </div>
        </div>
      </div>
    </header>
  );
};
