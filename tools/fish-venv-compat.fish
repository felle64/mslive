function source -a args
    for f in $args
        if test -f $f
            if string match -r '(^|/)(venv|.venv)/bin/activate$' $f
                if test -f $f.fish
                    source $f.fish
                else
                    source (dirname $f)/activate.fish
                end
                continue
            end
        end
        builtin source $f
    end
end

# Usage:
#   source tools/fish-venv-compat.fish
# or add the single line below to your ~/.config/fish/config.fish
#   source /absolute/path/to/repo/tools/fish-venv-compat.fish
