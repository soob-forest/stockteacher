'use client';

import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode } from 'react';

const navLinks = [
  { href: '/subscriptions', label: '구독 관리' },
  { href: '/reports', label: '리포트' },
  { href: '/reports/favorites', label: '즐겨찾기' }
];

function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <h1>StockTeacher</h1>
      <nav>
        {navLinks.map((link) => {
          const active = pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={active ? 'active' : undefined}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="page-shell">
          <Sidebar />
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
