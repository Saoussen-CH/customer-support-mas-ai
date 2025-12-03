import { AuthProvider } from './contexts/AuthContext';
import MainApp from './components/MainApp';

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
