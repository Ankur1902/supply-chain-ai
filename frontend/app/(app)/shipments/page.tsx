"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorState } from "@/components/error-state";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useShipments } from "@/hooks/api-hooks";
import { formatCurrency, formatDate } from "@/lib/utils";

const SHIPPING_MODES = ["Standard Class", "First Class", "Second Class", "Same Day"];
const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const PAGE_SIZE = 25;

export default function ShipmentsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [shippingMode, setShippingMode] = useState("");

  const { data, isLoading, isFetching, isError, refetch } = useShipments({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    risk_level: riskLevel || undefined,
    shipping_mode: shippingMode || undefined,
  });

  const shipments = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Shipment Explorer</h1>
        <p className="text-sm text-muted-foreground">
          {meta?.total ? `${meta.total.toLocaleString()} shipments` : "Loading…"}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search shipment code or product…"
            className="pl-8"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <NativeSelect
          className="w-40"
          value={riskLevel}
          onChange={(e) => {
            setRiskLevel(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All risk levels</option>
          {RISK_LEVELS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          className="w-44"
          value={shippingMode}
          onChange={(e) => {
            setShippingMode(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All shipping modes</option>
          {SHIPPING_MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </NativeSelect>
      </div>

      <div className="rounded-lg border bg-card">
        {isError ? (
          <ErrorState message="Couldn't load shipments." onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : shipments.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            No shipments match your filters.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Shipment</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Supplier</TableHead>
                <TableHead>Route</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Sales</TableHead>
                <TableHead>Risk</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className={isFetching ? "opacity-60" : ""}>
              {shipments.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link href={`/shipments/${s.id}`} className="font-medium text-primary hover:underline">
                      {s.shipment_code}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(s.order_date)}</TableCell>
                  <TableCell className="max-w-48 truncate">{s.product_name}</TableCell>
                  <TableCell className="max-w-40 truncate">{s.supplier_name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {s.origin_market} → {s.destination_region}
                  </TableCell>
                  <TableCell>{s.shipping_mode}</TableCell>
                  <TableCell>{formatCurrency(s.sales)}</TableCell>
                  <TableCell>
                    <RiskBadge level={s.risk_level} score={s.risk_score} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {meta && meta.total_pages && meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Page {meta.page} of {meta.total_pages}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="h-4 w-4" /> Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= (meta.total_pages ?? 1)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
