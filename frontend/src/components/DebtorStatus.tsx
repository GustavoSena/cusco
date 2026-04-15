import type { DebtorRecord } from "../types";

interface Props {
  debtor: DebtorRecord | null;
  isTaxDebtor: boolean;
}

export function DebtorStatus({ debtor, isTaxDebtor }: Props) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        Tax Debtor Status
        {isTaxDebtor ? (
          <span className="px-2 py-0.5 text-xs font-bold bg-red-100 text-red-700 rounded-full">
            DEBTOR
          </span>
        ) : (
          <span className="px-2 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded-full">
            CLEAR
          </span>
        )}
      </h3>

      {debtor?.found ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded">
          <p className="text-sm text-stone-700">
            Listed on the AT (Tax Authority) public debtor list.
          </p>
          {debtor.debt_bracket_label && (
            <p className="mt-2 text-lg font-semibold text-red-700">
              Debt bracket: {debtor.debt_bracket_label}
            </p>
          )}
        </div>
      ) : (
        <p className="text-stone-500 text-sm">
          No tax debts found on the AT public debtor list.
        </p>
      )}
    </div>
  );
}
