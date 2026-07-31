import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Stack } from '@mui/material';
import { ProductLayout } from '../layouts/ProductLayout';
import { pageRegistry, pageRegistryByPath } from '../routes/pageRegistry';
import { OperationsPage } from '../shared/components/OperationsPage';

function normalizePath(pathname: string) {
  if (!pathname || pathname === '/') return '/owner/dashboard';
  return pathname;
}

function App() {
  const [currentPath, setCurrentPath] = useState(() => normalizePath(window.location.pathname));
  const activePage = useMemo(() => pageRegistryByPath.get(currentPath), [currentPath]);

  useEffect(() => {
    const onPopState = () => setCurrentPath(normalizePath(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  function navigate(path: string) {
    window.history.pushState({}, '', path);
    setCurrentPath(path);
  }

  return (
    <ProductLayout currentPath={currentPath} onNavigate={navigate}>
      {activePage ? (
        <OperationsPage page={activePage} />
      ) : (
        <Stack spacing={2}>
          <Alert severity="error">مسیر یافت نشد. Request ID: ui-route-{Date.now()}</Alert>
          <Button onClick={() => navigate(pageRegistry[0].path)} variant="contained">بازگشت به اولین صفحه</Button>
        </Stack>
      )}
    </ProductLayout>
  );
}

export default App;
