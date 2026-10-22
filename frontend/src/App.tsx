import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { ProtectedRoute } from './components/layout/ProtectedRoute';

import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Customer Pages
import { CustomerDashboard } from './pages/customer/CustomerDashboard';
import { AccountsPage } from './pages/customer/AccountsPage';
import { TransfersPage } from './pages/customer/TransfersPage';
import { ProductsPage } from './pages/customer/ProductsPage';
import { PortfolioPage } from './pages/customer/PortfolioPage';
import { DisputesPage } from './pages/customer/DisputesPage';

// Staff Pages
import { StaffDashboard } from './pages/staff/StaffDashboard';
import { FraudTriagePage } from './pages/staff/FraudTriagePage';
import { GraphExplorerPage } from './pages/staff/GraphExplorerPage';
import { FraudLabPage } from './pages/staff/FraudLabPage';
import { AIHealthPage } from './pages/staff/AIHealthPage';
import { SystemAccountsPage } from './pages/staff/SystemAccountsPage';
import { AuditLogsPage } from './pages/staff/AuditLogsPage';
import { ReconciliationPage } from './pages/staff/ReconciliationPage';
import { ReportsAnalyticsPage } from './pages/staff/ReportsAnalyticsPage';
import { StaffDisputesPage } from './pages/staff/StaffDisputesPage';

const RootRedirect: React.FC = () => {
  const { isAuthenticated, isStaff, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isStaff) {
    return <Navigate to="/staff" replace />;
  }

  return <Navigate to="/dashboard" replace />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />

          {/* Root Redirect */}
          <Route path="/" element={<RootRedirect />} />

          {/* Customer Authenticated Routes */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute requiredRole="CUSTOMER">
                  <CustomerDashboard />
                </ProtectedRoute>
              }
            />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route
              path="/transfers"
              element={
                <ProtectedRoute requiredRole="CUSTOMER">
                  <TransfersPage />
                </ProtectedRoute>
              }
            />
            <Route path="/products" element={<ProductsPage />} />
            <Route
              path="/portfolio"
              element={
                <ProtectedRoute requiredRole="CUSTOMER">
                  <PortfolioPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/disputes"
              element={
                <ProtectedRoute requiredRole="CUSTOMER">
                  <DisputesPage />
                </ProtectedRoute>
              }
            />

            {/* Staff Authenticated Routes */}
            <Route
              path="/staff"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <StaffDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/fraud"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <FraudTriagePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/graph"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <GraphExplorerPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/fraud-lab"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <FraudLabPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/ai-health"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <AIHealthPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/disputes"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <StaffDisputesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/accounts"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <SystemAccountsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/audit"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <AuditLogsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/reconciliation"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <ReconciliationPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff/reports"
              element={
                <ProtectedRoute requiredRole="STAFF">
                  <ReportsAnalyticsPage />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* 404 Catch-All */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
