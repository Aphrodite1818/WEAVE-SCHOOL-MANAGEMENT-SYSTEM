import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { formatLimitValue } from "../../features/subscriptions/subscriptionConfig";
import Badge from "../ui/Badge";
import Button from "../ui/Button";

const limitItems = [
  ["Students", "students"],
  ["Teachers", "teachers"],
  ["Parents", "parents"],
];

function formatPrice(plan) {
  if (plan.planCode === "free") return plan.priceLabel || "₦0";
  if (plan.pricePerTerm === null || plan.pricePerTerm === undefined) {
    return plan.priceLabel || "Pricing unavailable";
  }
  return `₦${Number(plan.pricePerTerm).toLocaleString()}`;
}

function PublicPricingCard({ plan, selected = false, id, className = "" }) {
  const features = (plan.features || []).slice(0, 4);
  const price = formatPrice(plan);
  const compactPrice = /unavailable/i.test(price);

  return (
    <article
      id={id}
      className={`payment-plan-card flex h-full scroll-mt-28 flex-col rounded-3xl border bg-surface p-6 shadow-soft-card transition hover:border-primary/25 sm:p-8 ${
        selected || plan.highlighted
          ? "payment-plan-card-selected brand-strip-card border-primary/35 ring-1 ring-primary/10"
          : "border-border/70"
      } ${className}`}
    >
      <div className="flex min-h-8 items-start justify-between gap-4">
        <div>
          <h3 className="text-2xl font-semibold tracking-tight text-text">
            {plan.name}
          </h3>
          <p className="mt-2 text-sm text-text-muted">{plan.bestFor}</p>
        </div>
        {plan.highlighted ? (
          <Badge variant="primary">Popular</Badge>
        ) : null}
      </div>

      <div className="mt-8">
        <p
          className={`break-words font-semibold tracking-tight text-text ${
            compactPrice ? "text-2xl" : "text-4xl"
          }`}
        >
          {price}
        </p>
        <p className="mt-2 text-sm text-text-muted">Per academic term</p>
      </div>

      <p className="mt-6 min-h-[5.25rem] text-sm leading-7 text-text-muted">
        {plan.description}
      </p>

      <Link
        to="/register"
        className="mt-7 block"
      >
        <Button className="min-h-12 w-full rounded-xl">Get Started</Button>
      </Link>

      <div className="my-8 border-t border-border/70" />

      <p className="text-sm font-semibold text-text">Plan capacity</p>

      <dl className="mt-4 grid grid-cols-3 gap-4">
        {limitItems.map(([label, key]) => (
          <div key={key}>
            <dt className="text-xs font-medium text-text-muted">{label}</dt>
            <dd className="mt-1 text-lg font-semibold text-text">
              {formatLimitValue(plan.limits[key])}
            </dd>
          </div>
        ))}
      </dl>

      {features.length ? (
        <ul className="mt-7 space-y-3 border-t border-border/70 pt-7 text-sm text-text-soft">
          {features.map((feature) => (
            <li key={feature} className="flex items-start gap-3">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
              <span className="leading-5">{feature}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export default PublicPricingCard;
