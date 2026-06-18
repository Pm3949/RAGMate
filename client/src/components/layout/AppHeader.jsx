import React, { useState } from "react";
import { useLocation, Link } from "react-router-dom";
import {
  Search,
  Moon,
  Sun,
  Command,
  LogOut,
  Menu,
  ChevronRight,
  Home
} from "lucide-react";
import { toast } from "sonner";

import { useUIStore } from "../../store/useUIStore";
import { useAuth } from "../../context/AuthContext";
import NotificationBell from "./NotificationBell";
import UserProfileSheet from "./UserProfileSheet";

export default function AppHeader({
  onMenuClick,
}) {
  const darkMode = useUIStore((state) => state.darkMode);
  const toggleDarkMode = useUIStore((state) => state.toggleDarkMode);
  const setCommandPaletteOpen = useUIStore(
    (state) => state.setCommandPaletteOpen,
  );

  const { user } = useAuth();
  const location = useLocation();
  const [profileOpen, setProfileOpen] = useState(false);

  const displayName =
    user?.user_metadata?.full_name ||
    user?.email?.split("@")[0] ||
    "User";

  const avatarInitial = displayName
    .charAt(0)
    .toUpperCase();
  const commandShortcut =
    typeof navigator !== "undefined" &&
    /mac|iphone|ipad/i.test(navigator.platform)
      ? "Cmd K"
      : "Ctrl K";

  // Generate breadcrumbs from path
  const generateBreadcrumbs = () => {
    const pathnames = location.pathname.split("/").filter((x) => x);
    if (pathnames.length === 0) return [{ name: "Dashboard", path: "/dashboard" }];
    
    return pathnames.map((value, index) => {
      const to = `/${pathnames.slice(0, index + 1).join("/")}`;
      const name = value.charAt(0).toUpperCase() + value.slice(1).replace(/-/g, " ");
      return { name, path: to };
    });
  };

  const breadcrumbs = generateBreadcrumbs();

  return (
    <>
      <header className="h-16 bg-background/80 backdrop-blur-md sticky top-0 z-40 border-b border-border/50">
        <div className="h-full px-6 flex items-center justify-between">
          {/* LEFT: Breadcrumbs */}
          <div className="flex items-center gap-2">
            <button
              onClick={onMenuClick}
              type="button"
              className="h-9 w-9 rounded-md border border-border text-muted-foreground flex items-center justify-center hover:bg-muted hover:text-foreground lg:hidden mr-2"
            >
              <Menu size={16} />
            </button>

            <nav className="hidden md:flex items-center text-sm font-medium text-muted-foreground">
              <Link to="/dashboard" className="flex items-center hover:text-foreground transition-colors">
                <Home size={14} className="mr-1.5" />
              </Link>
              {breadcrumbs.map((crumb, idx) => (
                <div key={crumb.path} className="flex items-center">
                  <ChevronRight size={14} className="mx-1 opacity-50" />
                  <Link
                    to={crumb.path}
                    className={`hover:text-foreground transition-colors ${
                      idx === breadcrumbs.length - 1 ? "text-foreground font-semibold" : ""
                    }`}
                  >
                    {crumb.name}
                  </Link>
                </div>
              ))}
            </nav>
          </div>

          {/* RIGHT */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setCommandPaletteOpen(true)}
              className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border/50 bg-muted/30 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors text-sm w-48 lg:w-64"
            >
              <Search size={14} />
              <span className="flex-1 text-left">Search...</span>
              <kbd className="text-[10px] bg-background border border-border/50 rounded px-1.5 py-0.5 font-mono">{commandShortcut}</kbd>
            </button>

            <button
              onClick={toggleDarkMode}
              type="button"
              className="h-9 w-9 rounded-md border border-transparent text-muted-foreground flex items-center justify-center hover:bg-muted/50 hover:text-foreground transition-colors"
            >
              {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <NotificationBell />

            <div className="h-6 w-[1px] bg-border/50 mx-1"></div>

            <button 
              onClick={() => setProfileOpen(true)}
              className="flex items-center gap-2 pl-1 rounded-full cursor-pointer hover:bg-muted/50 transition-colors pr-3 py-1 outline-none"
            >
              <div className="h-8 w-8 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center justify-center font-semibold text-sm">
                {avatarInitial}
              </div>
              <span className="text-sm font-medium hidden sm:block">{displayName}</span>
            </button>
          </div>
        </div>
      </header>
      
      <UserProfileSheet open={profileOpen} onClose={() => setProfileOpen(false)} />
    </>
  );
}
