# flake.nix
{
  description = "build chatddx";
  inputs = {
    nixpkgs.url = "github:kompismoln/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
    }:
    let
      name = "chatddx";
      inherit (nixpkgs) lib;
      version = toString (self.shortRev or self.dirtyShortRev or self.lastModified or "unknown");
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$BACKEND_ROOT";
      };
      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python312;
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
            ]
          )
      );
      django-app =
        system: (pythonSets.${system}.mkVirtualEnv "${name}-django-${version}" workspace.deps.default);

      scripts =
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        pkgs.runCommand "chatddx-commands" { } ''
          mkdir -p $out/bin
          ln -s ${django-app system}/bin/chatddx $out/bin/chatddx
          ln -s ${django-app system}/bin/django $out/bin/chatddx-django
        '';

    in
    {
      inherit workspace pythonSets;

      packages = forAllSystems (system: {
        django-app = django-app system;
        scripts = scripts system;
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          # workspace.deps.all includes dev/test dependency-groups
          venv = pythonSet.mkVirtualEnv "${name}-venv" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            inherit name;
            packages = [
              venv
              pkgs.uv
              pkgs.basedpyright
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
              UV_VENV = "/dev/null";
            };
            shellHook = ''
              unset PYTHONPATH
              export BACKEND_ROOT=$(git rev-parse --show-toplevel)
              set -a
              source .env
              set +a
              echo "• Flake version: ${version}"
              echo "• Nixpkgs:       ${nixpkgs.shortRev}"
              echo "• Python path:   $UV_PYTHON"
              echo "===================================================="
            '';
          };
        }
      );
    };
}
