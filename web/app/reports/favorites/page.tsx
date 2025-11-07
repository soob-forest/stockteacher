'use client';

import { ReportsBoard } from '../../../components/ReportsBoard';

export default function FavoriteReportsPage() {
  return (
    <ReportsBoard
      title="즐겨찾는 리포트"
      initialFilter={{ favorites_only: true }}
      lockFavoritesOnly
    />
  );
}
