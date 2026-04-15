import type { EntityProfile } from "../types";

interface Props {
  profile: EntityProfile;
}

function formatEUR(value: number | null | undefined): string {
  if (value == null) return "-";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function EntityProfileCard({ profile }: Props) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        IMPIC Entity Profile
        {profile.country && (
          <span className="px-2 py-0.5 text-xs bg-stone-100 text-stone-600 rounded-full">
            {profile.country}
          </span>
        )}
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            Total Contracts
          </p>
          <p className="text-xl font-bold text-stone-900 mt-1">
            {profile.total_contracts ?? "-"}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            As Supplier
          </p>
          <p className="text-lg font-semibold text-stone-800 mt-1">
            {profile.times_as_supplier ?? "-"}
            <span className="text-sm font-normal text-stone-500 ml-1">times</span>
          </p>
          <p className="text-sm text-stone-600">
            {formatEUR(profile.total_value_as_supplier)}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            As Contracting Entity
          </p>
          <p className="text-lg font-semibold text-stone-800 mt-1">
            {profile.times_as_entity ?? "-"}
            <span className="text-sm font-normal text-stone-500 ml-1">times</span>
          </p>
          <p className="text-sm text-stone-600">
            {formatEUR(profile.total_value_as_entity)}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            Country
          </p>
          <p className="text-lg font-semibold text-stone-800 mt-1">
            {profile.country_code ?? "-"}
          </p>
          <p className="text-sm text-stone-600">{profile.country ?? ""}</p>
        </div>
      </div>
    </div>
  );
}
