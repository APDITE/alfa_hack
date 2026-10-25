import { useEffect, useMemo, useRef, useState } from "react";

import { api, errorText } from "../api/client";
import type { ApplicationDetail, BalancePoint, CashCalendarData, CashPreview, CashSimulation } from "../api/types";
import { gapDates } from "../utils/cash";
import { compactMoney, dayMonth, groupDigits, money, parseInteger } from "../utils/format";

type Row = { id: number; day: string; kind: "in" | "out"; amount: string; label: string };

let rowSeq = 0;
const nextId = () => {
  rowSeq += 1;
  return rowSeq;
};

const ALL_DAYS = Array.from({ length: 28 }, (_, i) => i + 1);

function toRows(calendar: CashCalendarData): Row[] {
  return calendar.events.map((event) => ({
    id: nextId(),
    day: String(event.day),
    kind: event.amount < 0 ? "out" : "in",
    amount: groupDigits(String(Math.abs(event.amount))),
    label: event.label,
  }));
}

function toCalendar(rows: Row[], opening: string, reserve: string): CashCalendarData {
  const events = rows.flatMap((row) => {
    const day = parseInteger(row.day);
    const amount = parseInteger(row.amount);
    if (day === null || day < 1 || day > 31 || !amount) return [];
    return [{ day, amount: row.kind === "in" ? amount : -amount, label: row.label.trim() }];
  });
  return { opening_balance: parseInteger(opening) ?? 0, reserve: parseInteger(reserve) ?? 0, events };
}

function Gap({ simulation }: { simulation: CashSimulation }) {
  return (
    <span className={`gap gap--${simulation.first_gap ? "bad" : "ok"}`}>
      {simulation.first_gap ? `не хватит до ${money(simulation.shortfall)}` : "разрыва нет"}
    </span>
  );
}

function signedMoney(value: number): string {
  return value < 0 ? `−${money(-value)}` : `+${money(value)}`;
}

function SimulationFact({ title, simulation }: { title: string; simulation: CashSimulation }) {
  const dates = gapDates(simulation);
  return (
    <div className={`cash__fact ${simulation.first_gap ? "is-bad" : "is-ok"}`}>
      <dt>{title}</dt>
      <dd>{simulation.first_gap ? `не хватит до ${money(simulation.shortfall)}` : "разрыва нет"}</dd>
      {dates && <dd className="cash__fact-note">{dates}</dd>}
    </div>
  );
}

/** Runs of days below the reserve, as [first index, last index]. */
function gapRuns(points: BalancePoint[], reserve: number): [number, number][] {
  const runs: [number, number][] = [];
  points.forEach((point, index) => {
    if (point.balance >= reserve) return;
    const last = runs[runs.length - 1];
    if (last && last[1] === index - 1) last[1] = index;
    else runs.push([index, index]);
  });
  return runs;
}

function BalanceChart({
  base,
  delayed,
  reserve,
}: {
  base: BalancePoint[];
  delayed: BalancePoint[] | null;
  reserve: number;
}) {
  if (base.length < 2) return null;
  const width = 860;
  const height = 240;
  const [left, right, top, bottom] = [76, 8, 10, 24];
  const values = [...base.map((p) => p.balance), ...(delayed ?? []).map((p) => p.balance), reserve, 0];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const x = (index: number) => left + (index / (base.length - 1)) * (width - left - right);
  const y = (value: number) => top + ((max - value) / (max - min || 1)) * (height - top - bottom);
  const line = (points: BalancePoint[]) =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.balance).toFixed(1)}`).join("");
  const band = (run: [number, number], kind: string) => (
    <rect
      key={`${kind}-${run[0]}`}
      className={`cash-chart__gap cash-chart__gap--${kind}`}
      x={x(run[0]) - 1}
      y={top}
      width={Math.max(3, x(run[1]) - x(run[0]) + 2)}
      height={height - top - bottom}
    />
  );
  // A tick at every month change; labels thinned out so that they do not overlap, with the
  // year wherever it changes.
  const starts = base.flatMap((point, index) =>
    index > 0 && point.day.slice(0, 7) !== base[index - 1].day.slice(0, 7) ? [index] : [],
  );
  const monthWidth = starts.length > 1 ? (x(starts[starts.length - 1]) - x(starts[0])) / (starts.length - 1) : width;
  const every = Math.max(1, Math.ceil(80 / monthWidth));
  let lastYear = "";
  const months = starts
    .filter((index, n) => n % every === 0 && x(index) < width - right - 40)
    .map((index) => {
      const day = new Date(`${base[index].day.slice(0, 10)}T12:00:00`);
      const year = String(day.getFullYear());
      const month = day.toLocaleDateString("ru-RU", { month: "short" });
      const label = year !== lastYear ? `${month} ${year}` : month;
      lastYear = year;
      return { index, label };
    });
  const gapDays = base.filter((p) => p.balance < reserve).length;

  return (
    <svg
      className="cash-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Остаток на счёте по дням: от ${compactMoney(min)} до ${compactMoney(max)}, дней с разрывом — ${gapDays}`}
    >
      {gapRuns(base, reserve).map((run) => band(run, "base"))}
      {delayed && gapRuns(delayed, reserve).map((run) => band(run, "delayed"))}
      {months.map(({ index, label }) => (
        <g key={index}>
          <line className="cash-chart__tick" x1={x(index)} x2={x(index)} y1={top} y2={height - bottom} />
          <text className="cash-chart__label" x={x(index) + 4} y={height - 7}>
            {label}
          </text>
        </g>
      ))}
      <line className="cash-chart__zero" x1={left} x2={width - right} y1={y(0)} y2={y(0)} />
      {reserve > 0 && (
        <line className="cash-chart__reserve" x1={left} x2={width - right} y1={y(reserve)} y2={y(reserve)} />
      )}
      <text className="cash-chart__label" x={left - 6} y={y(max) + 4} textAnchor="end">
        {compactMoney(max)}
      </text>
      {min < 0 && max > 0 && y(min) - y(0) > 16 && y(0) - y(max) > 16 && (
        <text className="cash-chart__label" x={left - 6} y={y(0) + 4} textAnchor="end">
          0 ₽
        </text>
      )}
      <text className="cash-chart__label" x={left - 6} y={y(min) + 4} textAnchor="end">
        {compactMoney(min)}
      </text>
      {delayed && <path className="cash-chart__line cash-chart__line--delayed" d={line(delayed)} />}
      <path className="cash-chart__line" d={line(base)} />
    </svg>
  );
}

type Props = {
  detail: ApplicationDetail;
  onSaved: (detail: ApplicationDetail) => void;
  onClose: () => void;
};

/** The client's typical month against the loan payment: gaps, receipts a week late, price of a day. */
export default function CashCalendar({ detail, onSaved, onClose }: Props) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [opening, setOpening] = useState("");
  const [reserve, setReserve] = useState("");
  const [day, setDay] = useState<number | null>(null);
  const [preview, setPreview] = useState<CashPreview | null>(null);
  const [showDelayed, setShowDelayed] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requestSeq = useRef(0);
  const lastKey = useRef("");

  // The saved calendar, or a template from the company's yearly revenue.
  useEffect(() => {
    let active = true;
    api
      .cashPreview(detail.id, {})
      .then((data) => {
        if (!active) return;
        lastKey.current = JSON.stringify({ calendar: data.calendar, day: data.payment_day });
        setPreview(data);
        setRows(toRows(data.calendar));
        setOpening(groupDigits(String(data.calendar.opening_balance)));
        setReserve(data.calendar.reserve ? groupDigits(String(data.calendar.reserve)) : "");
        setDay(data.payment_day);
      })
      .catch((caught: unknown) => {
        if (active) setError(errorText(caught));
      });
    return () => {
      active = false;
    };
  }, [detail.id]);

  const calendar = useMemo(() => (rows ? toCalendar(rows, opening, reserve) : null), [rows, opening, reserve]);

  // Recalculate shortly after every change; a late answer to an older request is ignored.
  useEffect(() => {
    if (!calendar || day === null) return undefined;
    const key = JSON.stringify({ calendar, day });
    if (key === lastKey.current) return undefined;
    const timer = window.setTimeout(() => {
      lastKey.current = key;
      requestSeq.current += 1;
      const mine = requestSeq.current;
      api
        .cashPreview(detail.id, { calendar, payment_day: day })
        .then((data) => {
          if (mine !== requestSeq.current) return;
          setPreview(data);
          setError("");
        })
        .catch((caught: unknown) => {
          if (mine === requestSeq.current) setError(errorText(caught));
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [calendar, day, detail.id]);

  function updateRow(id: number, change: Partial<Row>) {
    setRows((current) => (current ?? []).map((row) => (row.id === id ? { ...row, ...change } : row)));
  }

  async function save() {
    if (!calendar || day === null) return;
    setBusy(true);
    setError("");
    try {
      onSaved(await api.saveCashPlan(detail.id, calendar, day));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!rows || !preview || day === null || !calendar) {
    return (
      <div className="cash">
        <p className={error ? "form-error" : "muted"}>{error || "Считаем денежный поток…"}</p>
      </div>
    );
  }

  const selected = preview.options.find((o) => o.payment_day === preview.payment_day);
  const regular = detail.decision?.terms?.monthly_payment ?? null;
  const monthNet = preview.calendar.events.reduce((sum, event) => sum + event.amount, 0);

  return (
    <div className="cash">
      <div className="cash__head">
        <div>
          <h4>Денежный календарь</h4>
          <p className="muted small">
            Типичный месяц бизнеса: когда приходят деньги и когда вы платите. Банк проверит, хватит ли
            денег на платёж по кредиту в выбранный день — весь срок кредита.
          </p>
        </div>
        <button type="button" className="link-button" onClick={onClose}>
          Свернуть
        </button>
      </div>
      {preview.template && (
        <p className="cash__template">
          Это пример по годовой выручке компании — поправьте даты и суммы под свой бизнес.
        </p>
      )}

      <div className="cash__grid">
        <fieldset className="cash__month">
          <legend>Ваш месяц</legend>
          <div className="form-row">
            <label>
              Остаток на 1-е число, ₽
              <input inputMode="numeric" value={opening} onChange={(e) => setOpening(groupDigits(e.target.value))} />
            </label>
            <label>
              Неснижаемый резерв, ₽
              <input
                inputMode="numeric"
                value={reserve}
                placeholder="0"
                onChange={(e) => setReserve(groupDigits(e.target.value))}
              />
            </label>
          </div>
          <div className="table-wrap">
            <table className="cash__events">
              <colgroup>
                <col className="cash__col-day" />
                <col className="cash__col-kind" />
                <col className="cash__col-amount" />
                <col />
                <col className="cash__col-remove" />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Число</th>
                  <th scope="col">Что</th>
                  <th scope="col">Сумма, ₽</th>
                  <th scope="col">Описание</th>
                  <th scope="col">
                    <span className="visually-hidden">Удалить</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <input
                        className="cash__day-input"
                        aria-label="Число месяца"
                        inputMode="numeric"
                        maxLength={2}
                        value={row.day}
                        onChange={(e) => updateRow(row.id, { day: e.target.value.replace(/\D/g, "") })}
                      />
                    </td>
                    <td>
                      <select
                        aria-label="Поступление или расход"
                        value={row.kind}
                        onChange={(e) => updateRow(row.id, { kind: e.target.value as Row["kind"] })}
                      >
                        <option value="in">Поступление</option>
                        <option value="out">Расход</option>
                      </select>
                    </td>
                    <td>
                      <input
                        aria-label="Сумма"
                        inputMode="numeric"
                        value={row.amount}
                        onChange={(e) => updateRow(row.id, { amount: groupDigits(e.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        aria-label="Описание"
                        maxLength={60}
                        value={row.label}
                        onChange={(e) => updateRow(row.id, { label: e.target.value })}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Удалить строку ${row.label || row.day}`}
                        onClick={() => setRows((current) => (current ?? []).filter((r) => r.id !== row.id))}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            type="button"
            className="button button--secondary button--small"
            disabled={rows.length >= 40}
            onClick={() =>
              setRows((current) => [
                ...(current ?? []),
                { id: nextId(), day: "15", kind: "out", amount: "", label: "" },
              ])
            }
          >
            Добавить строку
          </button>
        </fieldset>

        <div className="cash__result">
          <div className="cash__chart-head">
            <h5>Остаток на счёте при платеже {preview.payment_day}-го числа — весь срок кредита</h5>
            <label className="checkbox">
              <input type="checkbox" checked={showDelayed} onChange={(e) => setShowDelayed(e.target.checked)} />
              Поступления на неделю позже
            </label>
          </div>
          <BalanceChart
            base={preview.chart_base}
            delayed={showDelayed ? preview.chart_delayed : null}
            reserve={calendar.reserve}
          />
          <ul className="cash__legend">
            <li>
              <span className="cash__swatch cash__swatch--line" aria-hidden="true" />
              остаток, как запланировано
            </li>
            {showDelayed && (
              <li>
                <span className="cash__swatch cash__swatch--delayed" aria-hidden="true" />
                поступления на неделю позже
              </li>
            )}
            <li>
              <span className="cash__swatch cash__swatch--gap" aria-hidden="true" />
              кассовый разрыв
            </li>
          </ul>
          {selected && (
            <dl className="cash__facts">
              <div className="cash__fact">
                <dt>Первый платёж</dt>
                <dd>
                  {dayMonth(selected.first_payment_date)} — {money(selected.first_payment)}
                </dd>
              </div>
              {regular !== null && (
                <div className={`cash__fact ${monthNet - regular < 0 ? "is-bad" : "is-ok"}`}>
                  <dt>За месяц после платежа</dt>
                  <dd>{signedMoney(monthNet - regular)}</dd>
                  <dd className="cash__fact-note">
                    поступления минус расходы — {signedMoney(monthNet)}, платёж — {money(regular)}
                  </dd>
                </div>
              )}
              <SimulationFact title="Как запланировано" simulation={selected.base} />
              <SimulationFact title="Поступления на неделю позже" simulation={selected.delayed} />
            </dl>
          )}
        </div>
      </div>

      <div className="cash__options">
        <h5>Сравнение дат платежа</h5>
        <div className="table-wrap">
          <table className="cash__compare">
            <thead>
              <tr>
                <th scope="col">День платежа</th>
                <th scope="col">Первый платёж</th>
                <th scope="col">Дороже на</th>
                <th scope="col">Как запланировано</th>
                <th scope="col">Поступления на неделю позже</th>
              </tr>
            </thead>
            <tbody>
              {preview.options.map((option) => (
                <tr key={option.payment_day} className={option.payment_day === day ? "is-selected" : undefined}>
                  <th scope="row">
                    <label className="cash__day">
                      <input
                        type="radio"
                        name={`payment-day-${detail.id}`}
                        checked={option.payment_day === day}
                        onChange={() => setDay(option.payment_day)}
                      />
                      {option.payment_day}-е
                      {option.payment_day === preview.recommended_day && (
                        <span className="badge badge--success">советуем</span>
                      )}
                    </label>
                  </th>
                  <td>{money(option.first_payment)}</td>
                  <td>{option.extra_cost ? `+${money(option.extra_cost)}` : "—"}</td>
                  <td>
                    <Gap simulation={option.base} />
                  </td>
                  <td>
                    <Gap simulation={option.delayed} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <label className="cash__other-day">
          Другой день
          <select value={day} onChange={(e) => setDay(Number(e.target.value))}>
            {ALL_DAYS.map((value) => (
              <option key={value} value={value}>
                {value}-е
              </option>
            ))}
          </select>
        </label>
        <p className="muted small">
          «Дороже на» — лишние проценты: первый платёж включает проценты со дня выдачи, и чем позже дата,
          тем дольше первый период.
        </p>
      </div>

      <p className="cash__advice">
        <strong>Совет банка.</strong> {preview.recommendation}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="button" className="button button--primary" disabled={busy} onClick={() => void save()}>
          {busy ? "Сохраняем…" : `Платить ${day}-го числа`}
        </button>
      </div>
    </div>
  );
}
