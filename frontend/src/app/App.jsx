import { BrowserRouter } from 'react-router-dom';
import { ToastProvider } from '../components/common/Toast';
import { HealthProvider } from '../hooks/useApiHealth';
import AppRoutes from './routes';

export default function App() {
  return <BrowserRouter><ToastProvider><HealthProvider><AppRoutes /></HealthProvider></ToastProvider></BrowserRouter>;
}
