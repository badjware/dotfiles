# Dotfiles
![xkcd 1806](https://imgs.xkcd.com/comics/borrow_your_laptop.png)

## Install
Clone the repository with the submodules and run the install script to symlink the files your `$HOME` directory:
```
git clone --recurse-submodules https://github.com/badjware/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
./install.sh
```

The install script supports some options. For exemple:

* Don't ask for confirmation: `./install.sh --yes`
* Copy instead of creating symlinks: `./install.sh --copy`

For a full list of options, run  `./install.sh --help`.

