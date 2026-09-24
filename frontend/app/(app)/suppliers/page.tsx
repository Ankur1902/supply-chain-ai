"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ErrorState } from "@/components/error-state";
import { ProvenanceBadge } from "@/components/provenance-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSuppliers } from "@/hooks/api-hooks";
import { formatPercent } from "@/lib/utils";

const PAGE_SIZE = 25;

export default function SuppliersPage() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("score");
  const { data, isLoading, isError, refetch } = useSuppliers({ page, page_size: PAGE_SIZE, sort_by: sortBy });

  const suppliers = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Supplier Intelligence</h1>
          <p className="text-sm text-muted-foreground">
            {meta?.total ? `${meta.total} suppliers` : "Loading…"} · <ProvenanceBadge kind="SYNTHETIC" /> demo
            enrichment layer
          </p>
        </div>
        <NativeSelect className="w-48" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="score">Sort by score</option>
          <option value="delay_rate">Sort by delay rate</option>
        </NativeSelect>
      </div>

      <div className="rounded-lg border bg-card">
        {isError ? (
          <ErrorState message="Couldn't load suppliers." onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Supplier</TableHead>
                <TableHead>Region</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Delay Rate</TableHead>
                <TableHead>Lead Time</TableHead>
                <TableHead>Volume</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {suppliers.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link href={`/suppliers/${s.id}`} className="font-medium text-primary hover:underline">
                      {s.supplier_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{s.supplier_region}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {s.supplier_tier}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-40 truncate">{s.product_category}</TableCell>
                  <TableCell className="font-medium tabular-nums">{s.score?.toFixed(0) ?? "—"}</TableCell>
                  <TableCell className="tabular-nums">{s.delay_rate !== null ? formatPercent(s.delay_rate) : "—"}</TableCell>
                  <TableCell className="tabular-nums">
                    {s.avg_lead_time_days !== null ? `${s.avg_lead_time_days.toFixed(1)}d` : "—"}
                  </TableCell>
                  <TableCell className="tabular-nums">{s.order_volume ?? "—"}</TableCell>
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
