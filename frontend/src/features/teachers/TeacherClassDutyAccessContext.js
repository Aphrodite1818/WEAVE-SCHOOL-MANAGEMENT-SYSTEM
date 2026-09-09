import { createContext, useContext } from "react";

export const TeacherClassDutyAccessContext = createContext({
  loading: false,
  hasClassTeacherDuties: false,
  error: null,
});

export function useTeacherClassDutyAccess() {
  return useContext(TeacherClassDutyAccessContext);
}
