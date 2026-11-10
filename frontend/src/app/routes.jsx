import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import DashboardPage from '../pages/DashboardPage';
import UploadPage from '../pages/UploadPage';
import DocumentsPage from '../pages/DocumentsPage';
import DocumentDetailPage from '../pages/DocumentDetailPage';
import DocumentPickerPage from '../pages/DocumentPickerPage';
import ProcessingPage from '../pages/ProcessingPage';
import ResultsPage from '../pages/ResultsPage';
import ValidationPage from '../pages/ValidationPage';
import HumanReviewPage from '../pages/HumanReviewPage';
import AnalyticsPage from '../pages/AnalyticsPage';
import { EmptyState } from '../components/common/States';

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/documents/upload" element={<UploadPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="/documents/:documentId/processing" element={<ProcessingPage />} />
        <Route path="/documents/:documentId/results" element={<ResultsPage />} />
        <Route path="/documents/:documentId/validation" element={<ValidationPage />} />
        <Route path="/processing" element={<DocumentPickerPage section="processing" title="AI Processing" subtitle="Pick a document to start or track its processing." />} />
        <Route path="/results" element={<DocumentPickerPage section="results" title="Extraction Results" subtitle="Pick a document to inspect its extracted data." />} />
        <Route path="/validation" element={<DocumentPickerPage section="validation" title="Validation & Reports" subtitle="Pick a document to inspect its validation report." />} />
        <Route path="/reviews" element={<HumanReviewPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="*" element={<EmptyState title="Page not found" to="/dashboard" cta="Go to Dashboard" />} />
      </Route>
    </Routes>
  );
}
