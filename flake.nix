{
  description = "tmux-ctl: REST API for tmux automation and AI agents";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        py = pkgs.python3.withPackages (ps: with ps; [
          fastapi
          uvicorn
          libtmux
        ]);
      in {
        devShells.default = pkgs.mkShell {
          packages = [ py pkgs.tmux ];
        };

        packages.default = pkgs.writeShellApplication {
          name = "tmux-ctl";
          runtimeInputs = [ py pkgs.tmux ];
          text = ''exec python3 ${./server.py} "$@"'';
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/tmux-ctl";
        };
      });
}
