import Badge from "../../../components/ui/Badge";
import { calendarStatusTone } from "../utils/calendarDisplay";

function CalendarStatusBadge({ status, children }) {
  const label = children || String(status || "unknown").replaceAll("_", " ");
  return <Badge variant={calendarStatusTone(status)}>{label}</Badge>;
}

export default CalendarStatusBadge;
