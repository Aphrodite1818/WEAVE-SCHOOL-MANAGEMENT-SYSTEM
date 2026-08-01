import { ArrowLeft, ArrowRight, CheckCircle2, Clock3, ExternalLink } from "lucide-react";

import Button from "../ui/Button";
import Modal from "../ui/Modal";
import GuideProgressStepper from "./GuideProgressStepper";

function RoleGuideModal({ guide }) {
  if (!guide?.config || !guide.currentStep) return null;

  const {
    config,
    steps,
    currentStep,
    currentIndex,
    open,
    previous,
    next,
    skipStep,
    remindLater,
    dismiss,
    openAction,
  } = guide;
  const Icon = currentStep.icon;
  const lastStep = currentIndex >= steps.length - 1;

  return (
    <Modal
      open={open}
      onClose={remindLater}
      title={config.title}
      description={config.description}
      className="max-w-3xl rounded-t-[1.6rem] sm:rounded-[1.6rem]"
      closeOnOverlay
      footer={(
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={dismiss}
            className="min-h-10 px-2 text-sm font-semibold text-text-muted transition hover:text-text"
          >
            Don’t show this guide again
          </button>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button type="button" variant="outline" onClick={remindLater}>
              <Clock3 className="h-4 w-4" />
              Remind me later
            </Button>
            <Button type="button" onClick={openAction}>
              {currentStep.actionLabel}
              <ExternalLink className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    >
      <div className="space-y-5">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-primary">
            {config.eyebrow}
          </p>
          <div className="mt-3">
            <GuideProgressStepper steps={steps} currentStepId={currentStep.id} />
          </div>
        </div>

        <section className="rounded-[1.35rem] border border-border bg-surface-muted/30 p-4 sm:p-5">
          <div className="flex items-start gap-3 sm:gap-4">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary sm:h-12 sm:w-12">
              {Icon ? <Icon className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-text-muted">
                  Step {currentIndex + 1}
                </span>
                {currentStep.complete ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2.5 py-1 text-[11px] font-bold text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Complete
                  </span>
                ) : null}
              </div>
              <h3 className="mt-3 text-xl font-semibold leading-tight text-text sm:text-2xl">
                {currentStep.label}
              </h3>
              <p className="mt-2 text-sm leading-6 text-text-muted">
                {currentStep.description}
              </p>
            </div>
          </div>
        </section>

        <div className="flex flex-col gap-2 border-t border-border/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            disabled={currentIndex === 0}
            onClick={previous}
          >
            <ArrowLeft className="h-4 w-4" /> Previous
          </Button>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button type="button" variant="outline" onClick={skipStep}>
              Skip this step
            </Button>
            <Button type="button" variant="outline" onClick={next}>
              {lastStep ? "Finish guide" : "Next step"}
              {!lastStep ? <ArrowRight className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default RoleGuideModal;
