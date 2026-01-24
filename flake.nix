{
  description = "FW16 Synth v2.0 - Professional FluidSynth controller for Framework 16 | DeMoD LLC";

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

        version = "2.0.0";

        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          evdev
          pyfluidsynth
        ]);

        # Runtime dependencies
        runtimeDeps = with pkgs; [
          fluidsynth
          soundfont-fluid
        ];

        # Main application package
        fw16-synth = pkgs.stdenv.mkDerivation {
          pname = "fw16-synth";
          inherit version;
          
          src = self;
          
          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = runtimeDeps;
          
          dontBuild = true;
          
          installPhase = ''
            runHook preInstall
            
            mkdir -p $out/bin $out/share/fw16-synth $out/share/applications
            
            # Install main script
            cp fw16_synth.py $out/share/fw16-synth/
            chmod +x $out/share/fw16-synth/fw16_synth.py
            
            # Install launcher script
            cp launch.sh $out/share/fw16-synth/ || true
            
            # Create wrapper with all dependencies
            makeWrapper ${pythonEnv}/bin/python3 $out/bin/fw16-synth \
              --add-flags "$out/share/fw16-synth/fw16_synth.py" \
              --prefix PATH : ${pkgs.lib.makeBinPath runtimeDeps} \
              --set DEFAULT_SOUNDFONT "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2" \
              --set PYTHONUNBUFFERED "1"
            
            # Desktop entry
            cat > $out/share/applications/fw16-synth.desktop << EOF
            [Desktop Entry]
            Type=Application
            Name=FW16 Synth
            Comment=Framework 16 Synthesizer Controller
            Exec=$out/bin/fw16-synth
            Terminal=true
            Categories=Audio;Music;Midi;
            Keywords=synthesizer;midi;music;fluidsynth;
            Icon=audio-x-generic
            EOF
            
            runHook postInstall
          '';
          
          meta = with pkgs.lib; {
            description = "Transform Framework 16 laptop into a professional synthesizer";
            longDescription = ''
              FW16 Synth is a low-latency FluidSynth controller that transforms
              your Framework 16 laptop into a performance synthesizer. Features
              include real-time TUI, SoundFont browser, arpeggiator, layer mode,
              and touchpad modulation.
            '';
            homepage = "https://github.com/ALH477/fw16-synth";
            license = licenses.mit;
            platforms = platforms.linux;
            maintainers = [];
            mainProgram = "fw16-synth";
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

        # Development shell
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
            python312Packages.pytest
          ];

          shellHook = ''
            export DEFAULT_SOUNDFONT="${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2"
            
            echo ""
            echo -e "\033[38;5;44m╔══════════════════════════════════════════════════════════════════════════╗\033[0m"
            echo -e "\033[38;5;44m║\033[0m  \033[1;38;5;51mFW16 Synth v${version}\033[0m - Development Shell                               \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m╠══════════════════════════════════════════════════════════════════════════╣\033[0m"
            echo -e "\033[38;5;44m║\033[0m  \033[38;5;135mDeMoD LLC\033[0m « Design ≠ Marketing »                                       \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m╠══════════════════════════════════════════════════════════════════════════╣\033[0m"
            echo -e "\033[38;5;44m║\033[0m  Run:       \033[1mpython fw16_synth.py\033[0m                                          \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m║\033[0m  Test:      \033[1mevtest\033[0m                                                        \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m║\033[0m  Format:    \033[1mblack fw16_synth.py\033[0m                                           \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m╠══════════════════════════════════════════════════════════════════════════╣\033[0m"
            echo -e "\033[38;5;44m║\033[0m  Features:  \033[38;5;135m[Tab]\033[0m SoundFonts  \033[38;5;135m[?]\033[0m Help  \033[38;5;135m[L]\033[0m Layer  \033[38;5;135m[A]\033[0m Arpeggiator       \033[38;5;44m║\033[0m"
            echo -e "\033[38;5;44m╚══════════════════════════════════════════════════════════════════════════╝\033[0m"
            echo ""
            
            if ! groups | grep -q '\binput\b'; then
              echo -e "\033[38;5;214m⚠  Not in 'input' group. Run: sudo usermod -aG input \$USER && logout\033[0m"
              echo ""
            fi
          '';
        };
      }
    ) // {
      # ═══════════════════════════════════════════════════════════════════════════
      # NixOS Module
      # ═══════════════════════════════════════════════════════════════════════════
      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth synthesizer controller";
            
            audioDriver = lib.mkOption {
              type = lib.types.enum [ "pipewire" "pulseaudio" "jack" "alsa" ];
              default = "pipewire";
              description = "Audio backend to use";
            };
            
            soundfont = lib.mkOption {
              type = lib.types.path;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
              description = "Default SoundFont file";
            };
            
            users = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Users to grant input device access";
            };
            
            enableRealtimeAudio = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable realtime audio scheduling for lower latency";
            };
          };

          config = lib.mkIf cfg.enable {
            environment.systemPackages = [
              self.packages.${pkgs.system}.default
              pkgs.evtest
            ];

            # Ensure input group exists
            users.groups.input = {};
            
            # Add users to required groups
            users.users = lib.genAttrs cfg.users (user: {
              extraGroups = [ "input" "audio" ];
            });

            # udev rules for input device access
            services.udev.extraRules = ''
              # FW16 Synth - Input device access
              SUBSYSTEM=="input", GROUP="input", MODE="0660"
              SUBSYSTEM=="input", ATTRS{name}=="*Framework*", GROUP="input", MODE="0660"
              SUBSYSTEM=="input", ATTRS{name}=="*Touchpad*", GROUP="input", MODE="0660"
              SUBSYSTEM=="input", ATTRS{name}=="*Keyboard*", GROUP="input", MODE="0660"
            '';

            # Realtime audio support
            security.rtkit.enable = cfg.enableRealtimeAudio;
            
            security.pam.loginLimits = lib.mkIf cfg.enableRealtimeAudio [
              { domain = "@audio"; type = "-"; item = "rtprio"; value = "95"; }
              { domain = "@audio"; type = "-"; item = "memlock"; value = "unlimited"; }
              { domain = "@audio"; type = "-"; item = "nice"; value = "-19"; }
            ];
          };
        };

      # ═══════════════════════════════════════════════════════════════════════════
      # Home-Manager Module  
      # ═══════════════════════════════════════════════════════════════════════════
      homeManagerModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.fw16-synth;
        in {
          options.programs.fw16-synth = {
            enable = lib.mkEnableOption "FW16 Synth";
            
            soundfont = lib.mkOption {
              type = lib.types.str;
              default = "${pkgs.soundfont-fluid}/share/soundfonts/FluidR3_GM.sf2";
              description = "Default SoundFont file";
            };
            
            audioDriver = lib.mkOption {
              type = lib.types.enum [ "pipewire" "pulseaudio" "jack" "alsa" ];
              default = "pipewire";
              description = "Audio backend";
            };
            
            defaultOctave = lib.mkOption {
              type = lib.types.int;
              default = 4;
              description = "Starting octave (0-8)";
            };
            
            defaultProgram = lib.mkOption {
              type = lib.types.int;
              default = 0;
              description = "Starting GM program (0-127)";
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [ self.packages.${pkgs.system}.default ];
            
            xdg.desktopEntries.fw16-synth = {
              name = "FW16 Synth";
              comment = "Framework 16 Synthesizer Controller";
              exec = "fw16-synth --driver ${cfg.audioDriver} --octave ${toString cfg.defaultOctave} --program ${toString cfg.defaultProgram}";
              terminal = true;
              categories = [ "Audio" "Music" "Midi" ];
              icon = "audio-x-generic";
              settings = {
                Keywords = "synthesizer;midi;music;fluidsynth;framework;";
              };
            };
            
            # Ensure config directory exists
            xdg.configFile."fw16-synth/.keep".text = "# FW16 Synth config directory\n";
          };
        };
      
      # Backwards compatibility alias
      homeModules.default = self.homeManagerModules.default;
    };
}
