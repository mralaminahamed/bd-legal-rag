import { Card, CardContent, CardHeader, CardTitle } from "./card";

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
}

export function StatCard({ title, value, sub }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
