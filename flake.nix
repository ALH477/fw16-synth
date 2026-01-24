{
  description = "FW16 Synth - Professional FluidSynth controller for Framework 16";

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

        # Main application
        fw16-synth = pkgs.stdenv.mkDerivation {
          pname = "fw16-synth";
          version = "2.0.0";
          src = ./.;
          
          nativeBuildInputs = [ pkgs.makeWrapper ];
          
          installPhase = ''
            mkdir -p $out/bin $out/share/fw16-synth
            cp fw16_synth.py $out/share/fw16-synth/
            
            makeWrapper ${pythonEnv}/bin/python3 $out/bin/fw16-synth \
              --add-flags "$out/share/fw16-synth/fw16_synth.py" \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.fluidsynth ]} \
              --set DEFAULT_SOUNDFONT "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2"
          '';
          
          meta = with pkgs.lib; {
            description = "Transform Framework 16 into a synthesizer";
            license = licenses.mit;
            platforms = platforms.linux;
          };
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
            pythonEnv
            fluidsynth
            soundfont-fluid
            soundfont-generaluser
            pipewire
            pipewire.pulse
            jack2
            alsa-utils
            evtest
            libinput
            python312Packages.black
            python312Packages.mypy
          ];

          shellHook = ''
            echo ""
            echo "╔══════════════════════════════════════════════════════════════╗"
            echo "║  FW16 Synth v2.0 - Development Shell                         ║"
            echo "╠══════════════════════════════════════════════════════════════╣"
            echo "║  Run:     python fw16_synth.py                               ║"
            echo "║  Test:    evtest                                             ║"
            echo "║  Format:  black fw16_synth.py                                ║"
            echo "╠══════════════════════════════════════════════════════════════╣"
            echo "║  New: [Tab] SoundFont Browser  [?] Help  [L] Layer  [A] Arp  ║"
            echo "╚══════════════════════════════════════════════════════════════╝"
            echo ""
            
            export DEFAULT_SOUNDFONT="${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2"
            
            if ! groups | grep -q input; then
              echo "⚠  Add yourself to 'input' group: sudo usermod -aG input \$USER"
              echo ""
            fi
          '';
        };
      }
    ) // {
      # NixOS Module
      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth synthesizer controller";
            
            audioDriver = lib.mkOption {
              type = lib.types.enum [ "pipewire" "pulseaudio" "jack" "alsa" ];
              default = "pipewire";
              description = "Audio backend";
            };
            
            soundfont = lib.mkOption {
              type = lib.types.path;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
              description = "Default soundfont";
            };
            
            users = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Users to grant input device access";
            };
            
            enableRealtimeAudio = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable realtime audio scheduling";
            };
          };

          config = lib.mkIf cfg.enable {
            environment.systemPackages = [
              self.packages.${pkgs.system}.default
              pkgs.evtest
            ];

            users.groups.input = {};
            
            users.users = lib.genAttrs cfg.users (user: {
              extraGroups = [ "input" "audio" ];
            });

            services.udev.extraRules = ''
              SUBSYSTEM=="input", GROUP="input", MODE="0660"
              SUBSYSTEM=="input", ATTRS{name}=="*Framework*", GROUP="input", MODE="0660"
              SUBSYSTEM=="input", ATTRS{name}=="*Touchpad*", GROUP="input", MODE="0660"
            '';

            security.rtkit.enable = cfg.enableRealtimeAudio;
            
            security.pam.loginLimits = lib.mkIf cfg.enableRealtimeAudio [
              { domain = "@audio"; type = "-"; item = "rtprio"; value = "95"; }
              { domain = "@audio"; type = "-"; item = "memlock"; value = "unlimited"; }
              { domain = "@audio"; type = "-"; item = "nice"; value = "-19"; }
            ];
          };
        };

      # Home-Manager Module
      homeModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth";
            
            soundfont = lib.mkOption {
              type = lib.types.str;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
            };
            
            audioDriver = lib.mkOption {
              type = lib.types.enum [ "pipewire" "pulseaudio" "jack" "alsa" ];
              default = "pipewire";
            };
            
            defaultOctave = lib.mkOption {
              type = lib.types.int;
              default = 4;
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [ self.packages.${pkgs.system}.default ];
            
            xdg.desktopEntries.fw16-synth = {
              name = "FW16 Synth";
              comment = "Framework 16 Synthesizer";
              exec = "fw16-synth --driver ${cfg.audioDriver}";
              terminal = true;
              categories = [ "Audio" "Music" "Midi" ];
              icon = "audio-x-generic";
            };
            
            # Create config directory
            xdg.configFile."fw16-synth/.keep".text = "";
          };
        };
    };
}
