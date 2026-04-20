interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  /**
   * Optional description read by assistive tech alongside the label.
   * Visible description should be supplied by the parent if needed.
   */
  description?: string;
  /**
   * Optional small adornment (emoji, icon) rendered before the label —
   * used to distinguish toggles in dense UIs at a glance.
   */
  adornment?: React.ReactNode;
  disabled?: boolean;
}

/**
 * Compact in-line switch styled to blend into the app header.
 *
 * Rendered as a real `<button role="switch">` so keyboard users get
 * space/enter activation for free and screen readers announce the
 * on/off state. The visible label is wired via `aria-label`.
 */
export function ToggleSwitch({
  checked,
  onChange,
  label,
  description,
  adornment,
  disabled = false,
}: Props) {
  return (
    <label
      className={`inline-flex items-center gap-2 text-xs ${
        disabled ? "opacity-50" : "cursor-pointer"
      }`}
    >
      <span className="flex items-center gap-1 text-stone-600">
        {adornment}
        <span>{label}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        aria-describedby={description ? `${label}-desc` : undefined}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 ${
          checked ? "bg-brand-600" : "bg-stone-300"
        } ${disabled ? "cursor-not-allowed" : ""}`}
      >
        <span
          className={`inline-block h-3 w-3 transform rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-3.5" : "translate-x-0.5"
          }`}
        />
      </button>
      {description && (
        <span id={`${label}-desc`} className="sr-only">
          {description}
        </span>
      )}
    </label>
  );
}
