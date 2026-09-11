import { GraduationCap } from "lucide-react";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/shared/EmptyState";
import { displayName } from "../../utils/user";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";
import { normalizeParentChildRecord } from "./parentPageUtils";

function ParentChildSelector({
  linkedChildren = [],
  selectedChildId,
  onSelectChild,
  academicLabel = "-",
  showCards = true,
}) {
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={linkedChildren.length > 0 ? "success" : "warning"}>
          {linkedChildren.length > 0 ? "Linked children available" : "No linked children"}
        </Badge>
        <Badge variant="info">{academicLabel}</Badge>
      </div>

      {showCards && (
        <div className="mobile-scroll-list grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {linkedChildren.length > 0 ? (
            linkedChildren.map((entry, index) => {
              const { student, link } = normalizeParentChildRecord(entry);
              const studentId = student?.id;
              const isActive = studentId === selectedChildId;
              return (
                <button
                  key={link.id || studentId || `linked-child-${index}`}
                  type="button"
                  onClick={() => studentId && onSelectChild(studentId)}
                  disabled={!studentId}
                  className={cn(
                    "rounded-[1.2rem] border px-4 py-3 text-left transition",
                    isActive
                      ? "border-primary bg-primary shadow-md"
                      : "border-border/70 bg-surface-muted/15 hover:border-primary/30 hover:bg-surface-muted/50"
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className={cn("whitespace-normal break-words text-sm font-semibold leading-5 sm:truncate", isActive ? "text-primary-foreground" : "text-text")}>
                        {displayName(student)}
                      </p>
                      <p className={cn("mt-1 break-words text-xs leading-5", isActive ? "text-primary-foreground" : "text-text-muted")}>
                        {cleanText(student?.admission_number)} / {cleanText(student?.profile_status || student?.status)}
                      </p>
                    </div>
                    <Badge variant={isActive ? "default" : (link.is_primary_contact ? "success" : "default")} className={cn(isActive && "bg-primary text-primary-foreground border-current")}>
                      {cleanText(link.relationship_type || "linked")}
                    </Badge>
                  </div>
                </button>
              );
            })
          ) : (
            <div className="col-span-full">
              <EmptyState
                icon={GraduationCap}
                title="No linked students yet"
                description="Link a student from the Student Linking page to start tracking their academic progress."
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ParentChildSelector;
