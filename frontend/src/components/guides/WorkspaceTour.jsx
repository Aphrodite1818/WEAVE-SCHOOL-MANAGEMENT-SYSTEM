import { ArrowLeft, ArrowRight, Check, Compass, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { navGroups } from "../layout/navConfig";
import { tourContentForItem } from "../../features/guides/workspaceTourContent";
import { getErrorMessage } from "../../services/api";
import Button from "../ui/Button";
import WorkspaceTourSnapshot from "./WorkspaceTourSnapshot";
import "./workspaceTour.css";

const focusable = 'button:not([disabled]), a[href], [tabindex="0"]';
const clamp = (value, min, max) => Math.max(min, Math.min(value, Math.max(min, max)));

function connectorGeometry(card, target) {
  if (!card || !target) return null;
  const targetX = target.left + target.width + 2;
  const targetY = target.top + target.height / 2;
  const targetIsLeft = targetX < card.left;
  const startX = targetIsLeft ? card.left - 8 : card.left + card.width + 8;
  const startY = card.top + Math.min(Math.max(card.height * 0.42, 100), card.height - 90);
  const distance = Math.abs(startX - targetX);
  const bend = Math.max(80, distance * 0.48);
  const controlOneX = targetIsLeft ? startX - bend : startX + bend;
  const controlTwoX = targetIsLeft ? targetX + Math.max(52, distance * 0.24) : targetX - Math.max(52, distance * 0.24);
  return {
    path: `M ${startX} ${startY} C ${controlOneX} ${startY}, ${controlTwoX} ${targetY}, ${targetX} ${targetY}`,
  };
}

export default function WorkspaceTour({ role, onClose, onSetup }) {
  const [steps, setSteps] = useState([]);
  const [index, setIndex] = useState(-1);
  const [geometry, setGeometry] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const overlayRef = useRef(null);
  const cardRef = useRef(null);
  const headingRef = useRef(null);
  const actionLock = useRef(false);
  const step = steps[index];
  const welcome = index < 0;
  const last = index === steps.length - 1;
  const Icon = step?.icon || Compass;
  const visibleRoutes = steps.map((item) => item.to);

  useLayoutEffect(() => {
    const configured = (navGroups[role] || []).flatMap((group) => group.items);
    // The rendered navigation is the canonical release/plan view for the tour.
    // Hidden desktop/mobile duplicates and runtime-disabled features are ignored.
    const rendered = new Set(
      Array.from(document.querySelectorAll("[data-tour-target]"))
        .filter((node) => node.getBoundingClientRect().width > 0)
        .map((node) => node.dataset.tourTarget),
    );
    setSteps(
      configured
        .filter((item) => rendered.has(item.to))
        .map((item) => tourContentForItem(role, item)),
    );
  }, [role]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const siblings = Array.from(document.body.children)
      .filter((node) => node !== overlayRef.current && node instanceof HTMLElement)
      .map((node) => [node, node.inert]);
    siblings.forEach(([node]) => { node.inert = true; });
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    headingRef.current?.focus({ preventScroll: true });
    return () => {
      siblings.forEach(([node, inert]) => { node.inert = inert; });
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, []);

  useLayoutEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
    let frame;
    const getTarget = () => step && Array.from(document.querySelectorAll("[data-tour-target]"))
      .find((node) => node.dataset.tourTarget === step.to && node.getBoundingClientRect().width > 0);
    const target = getTarget();
    const nav = target?.closest("nav");
    const originalScroll = nav?.scrollTop;
    if (target && nav) {
      nav.scrollTop += target.getBoundingClientRect().top - nav.getBoundingClientRect().top - 12;
    }

    const measure = () => {
      const rect = getTarget()?.getBoundingClientRect();
      const viewport = window.visualViewport;
      const width = viewport?.width || window.innerWidth;
      const height = viewport?.height || window.innerHeight;
      const top = viewport?.offsetTop || 0;
      const mobile = width < 768;
      const navRect = nav?.parentElement?.getBoundingClientRect();
      const usableLeft = mobile ? 0 : Math.max(16, Math.min(navRect?.right || 0, width * 0.34) + 20);
      const availableWidth = Math.max(320, width - usableLeft - 32);
      const cardWidth = Math.min(500, availableWidth);
      const cardHeight = cardRef.current?.offsetHeight || 520;
      const hasTarget = Boolean(rect && rect.bottom > top && rect.top < top + height);
      const cardLeft = mobile ? 0 : clamp(
        usableLeft + (width - usableLeft - cardWidth) / 2,
        usableLeft + 16,
        width - cardWidth - 16,
      );
      const cardTop = mobile ? 0 : clamp(
        top + (height - cardHeight) / 2,
        top + 20,
        top + height - cardHeight - 20,
      );
      const targetBox = hasTarget
        ? { left: rect.left - 5, top: rect.top - 5, width: rect.width + 10, height: rect.height + 10 }
        : null;
      const cardBox = mobile ? null : { left: cardLeft, top: cardTop, width: cardWidth, height: cardHeight };
      const next = {
        mobile,
        viewport: { width, height },
        target: targetBox,
        card: mobile ? {} : { width: cardWidth, left: cardLeft, top: cardTop },
        connector: !mobile && targetBox && !welcome ? connectorGeometry(cardBox, targetBox) : null,
      };
      setGeometry((current) => JSON.stringify(current) === JSON.stringify(next) ? current : next);
    };

    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    measure();
    const observer = new ResizeObserver(schedule);
    if (cardRef.current) observer.observe(cardRef.current);
    if (target) observer.observe(target);
    window.addEventListener("resize", schedule);
    window.addEventListener("scroll", schedule, true);
    window.visualViewport?.addEventListener("resize", schedule);
    window.visualViewport?.addEventListener("scroll", schedule);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      window.removeEventListener("scroll", schedule, true);
      window.visualViewport?.removeEventListener("resize", schedule);
      window.visualViewport?.removeEventListener("scroll", schedule);
      if (nav) nav.scrollTop = originalScroll;
    };
  }, [step, welcome]);

  const finish = async (completed, setup = false) => {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    setError("");
    try {
      await onClose(completed);
      if (setup) onSetup();
    } catch (err) {
      setError(getErrorMessage(err, "Could not save your tour preference. Please try again."));
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  };

  const onKeyDown = (event) => {
    if (event.key === "Escape") { event.preventDefault(); finish(false); }
    if (event.key !== "Tab") return;
    const controls = Array.from(cardRef.current?.querySelectorAll(focusable) || []);
    const first = controls[0];
    const final = controls.at(-1);
    if (event.shiftKey && (document.activeElement === first || document.activeElement === headingRef.current)) {
      event.preventDefault();
      final?.focus();
    } else if (!event.shiftKey && document.activeElement === final) {
      event.preventDefault();
      first?.focus();
    }
  };

  return createPortal(
    <div ref={overlayRef} className="workspace-tour" onKeyDown={onKeyDown}>
      {geometry?.target && !welcome
        ? <div aria-hidden="true" className="workspace-tour-spotlight" style={geometry.target} />
        : <div className="workspace-tour-dimmer" />}
      {geometry?.connector ? (
        <svg
          aria-hidden="true"
          className="workspace-tour-connector"
          width={geometry.viewport.width}
          height={geometry.viewport.height}
          viewBox={`0 0 ${geometry.viewport.width} ${geometry.viewport.height}`}
        >
          <defs>
            <marker id="workspace-tour-arrowhead" markerWidth="12" markerHeight="12" refX="9" refY="6" orient="auto" markerUnits="strokeWidth">
              <path d="M 0 0 L 10 6 L 0 12 z" className="workspace-tour-arrowhead" />
            </marker>
          </defs>
          <path className="workspace-tour-connector-shadow" d={geometry.connector.path} />
          <path className="workspace-tour-connector-line" d={geometry.connector.path} markerEnd="url(#workspace-tour-arrowhead)" />
        </svg>
      ) : null}
      <section
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-tour-title"
        aria-describedby="workspace-tour-description"
        className="workspace-tour-card"
        style={geometry?.card}
      >
        <div className="workspace-tour-body">
          <div className="flex items-center justify-between gap-4">
            <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
              {welcome ? "Welcome to Weave" : `Your workspace · ${index + 1} of ${steps.length}`}
            </span>
            <button type="button" disabled={busy} onClick={() => finish(false)} aria-label="Close tour" className="workspace-tour-close">
              <X className="h-5 w-5" />
            </button>
          </div>
          {!welcome ? (
            <div className="mt-4 h-1 overflow-hidden rounded-full bg-surface-muted" role="progressbar" aria-label="Tour progress" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={index + 1}>
              <div className="h-full bg-primary motion-safe:transition-[width]" style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
            </div>
          ) : null}
          <div className="mt-6 flex items-center gap-3 text-primary">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft"><Icon className="h-5 w-5" /></span>
            <span className="text-sm font-semibold">{step?.label || "A little guidance, a confident start"}</span>
          </div>
          <h2 ref={headingRef} tabIndex={-1} id="workspace-tour-title" className="mt-4 text-2xl font-semibold leading-tight tracking-tight text-text outline-none">
            {step?.title || "Find your way around."}
          </h2>
          <p id="workspace-tour-description" className="mt-3 text-sm leading-7 text-text-muted">
            {step?.description || (role === "admin"
              ? "Take a quick look around your workspace. Then we’ll help you prepare your session, first term, and calendar."
              : "Get to know the places you’ll use in your school workspace. There’s nothing to fill in—just take a look around.")}
          </p>
          {step ? (
            <div className="workspace-tour-preview">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">A quick look inside {step.label}</p>
              <WorkspaceTourSnapshot step={step} visibleRoutes={visibleRoutes} />
              <ul className="mt-4 grid gap-2 sm:grid-cols-3">
                {step.preview.map((label) => (
                  <li key={label} className="flex items-center gap-2 text-xs font-medium text-text">
                    <Check className="h-3.5 w-3.5 shrink-0 text-primary" />{label}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-6 text-sm font-medium text-text">You can skip this tour or replay it later from Settings.</p>
          )}
          {error ? <p role="alert" className="mt-4 text-sm text-error">{error}</p> : null}
        </div>
        <footer className="workspace-tour-footer">
          <div className="flex items-center justify-between gap-2">
            <Button variant="ghost" disabled={busy} onClick={() => welcome ? finish(false, role === "admin") : setIndex(index - 1)}>
              {welcome ? (role === "admin" ? "Skip to setup" : "Skip tour") : <><ArrowLeft className="h-4 w-4" />Back</>}
            </Button>
            <Button disabled={busy || (welcome && !steps.length)} onClick={() => last && !welcome ? finish(true, role === "admin") : setIndex(index + 1)}>
              {busy ? "Saving…" : welcome ? "Show me around" : last ? (role === "admin" ? "Set up school year" : "Go to dashboard") : "Next"}<ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          {!welcome ? (
            <button type="button" disabled={busy} onClick={() => finish(false, role === "admin")} className="workspace-tour-secondary-action">
              {role === "admin" ? "Skip to school setup" : "Skip tour"}
            </button>
          ) : null}
        </footer>
      </section>
    </div>,
    document.body,
  );
}
