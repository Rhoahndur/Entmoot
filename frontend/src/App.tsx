import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { UploadPage } from './pages/UploadPage';
import { ConfigPage } from './pages/ConfigPage';
import { ResultsPage } from './pages/ResultsPage';
import { ProjectsListPage } from './pages/ProjectsListPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/projects" element={<ProjectsListPage />} />
      </Routes>
    </Router>
  );
}

export default App;
