{
  description = "FW16 Synth - FluidSynth controller using Framework 16 keyboard and touchpad";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { 
          inherit system; 
          config.allowUnfree = true;
        };

        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          evdev
          pyfluidsynth
        ]);

        fw16-synth = pkgs.writeShellApplication {
          name = "fw16-synth";
          runtimeInputs = [ 
            pythonEnv 
            pkgs.fluidsynth
            pkgs.soundfont-fluid  # FluidR3 GM soundfont
          ];
          text = ''
            # Default soundfont location
            DEFAULT_SF="${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2"
            
            # Run with default soundfont if not specified
            if [[ "$*" != *"--soundfont"* ]] && [[ "$*" != *"-s"* ]]; then
              exec python3 ${./fw16_synth.py} --soundfont "$DEFAULT_SF" "$@"
            else
              exec python3 ${./fw16_synth.py} "$@"
            fi
          '';
        };

      in {
        packages = {
          default = fw16-synth;
          fw16-synth = fw16-synth;
        };

        apps.default = {
          type = "app";
          program = "${fw16-synth}/bin/fw16-synth";
        };

        devShells.default = pkgs.mkShell {
          name = "fw16-synth-dev";
          
          packages = with pkgs; [
            # Python environment
            pythonEnv
            
            # FluidSynth and audio
            fluidsynth
            soundfont-fluid
            soundfont-generaluser
            
            # Audio backends
            pipewire
            pipewire.pulse
            jack2
            
            # Development tools
            python312Packages.black
            python312Packages.mypy
            python312Packages.pytest
          ];

          shellHook = ''
            echo "╔════════════════════════════════════════════════════════════╗"
            echo "║  FW16 Synth Development Shell                              ║"
            echo "║  Framework 16 → Synthesizer Controller                     ║"
            echo "╠════════════════════════════════════════════════════════════╣"
            echo "║  Run:  python fw16_synth.py                                ║"
            echo "║  Or:   nix run                                             ║"
            echo "╚════════════════════════════════════════════════════════════╝"
            
            # Set default soundfont
            export DEFAULT_SOUNDFONT="${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2"
            echo "Soundfont: $DEFAULT_SOUNDFONT"
          '';
        };
      }
    ) // {
      # NixOS module for system-wide installation
      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth - Framework 16 synthesizer";
            
            audioDriver = lib.mkOption {
              type = lib.types.enum [ "pulseaudio" "pipewire" "jack" "alsa" ];
              default = "pipewire";
              description = "Audio backend to use";
            };
            
            soundfont = lib.mkOption {
              type = lib.types.path;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
              description = "Path to SoundFont file";
            };
            
            extraGroups = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [ "input" "audio" ];
              description = "Groups for device access";
            };
          };

          config = lib.mkIf cfg.enable {
            # Ensure input device access
            users.groups.input = {};
            
            # udev rules for non-root touchpad/keyboard access
            services.udev.extraRules = ''
              # Allow input group to access input devices
              SUBSYSTEM=="input", GROUP="input", MODE="0660"
              
              # Framework 16 specific (adjust vendor/product as needed)
              SUBSYSTEM=="input", ATTRS{name}=="*Framework*", GROUP="input", MODE="0660"
            '';

            environment.systemPackages = [
              self.packages.${pkgs.system}.default
            ];
          };
        };

      # Home-manager module
      homeModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth";
            
            soundfont = lib.mkOption {
              type = lib.types.str;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
              description = "Default soundfont";
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [ self.packages.${pkgs.system}.default ];
            
            # Desktop entry
            xdg.desktopEntries.fw16-synth = {
              name = "FW16 Synth";
              comment = "Turn your Framework 16 into a synthesizer";
              exec = "fw16-synth --soundfont ${cfg.soundfont}";
              terminal = true;
              categories = [ "Audio" "Music" ];
              icon = "audio-x-generic";
            };
          };
        };
    };
}
