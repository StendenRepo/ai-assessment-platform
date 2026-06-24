import { useAuth } from '@/context/AuthContext';

export function isModuleViewOnly(user, moduleTeacherId) {
  return Boolean(
    user?.is_admin && moduleTeacherId && moduleTeacherId !== user?.id
  );
}

export function useModuleViewOnly(moduleTeacherId) {
  const { user } = useAuth();
  return isModuleViewOnly(user, moduleTeacherId);
}
