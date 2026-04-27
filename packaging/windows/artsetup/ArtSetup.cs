using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Forms;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Brushes = System.Windows.Media.Brushes;
using Button = System.Windows.Controls.Button;
using MessageBox = System.Windows.MessageBox;
using TextBox = System.Windows.Controls.TextBox;
using WpfApplication = System.Windows.Application;
using WpfPath = System.Windows.Shapes.Path;
using WpfProgressBar = System.Windows.Controls.ProgressBar;

namespace GPT2JSON.ArtSetup
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            var app = new WpfApplication();            app.Run(new InstallerWindow());
        }
    }

    public sealed class InstallerWindow : Window
    {
        private const string AppName = "GPT2JSON";
        private const string Version = "v0.1.0";
        private readonly TextBox _dirBox;
        private readonly Button _installButton;
        private readonly WpfProgressBar _progress;
        private readonly TextBlock _status;
        private readonly Button _closeButton;
        private readonly Button _minButton;

        public InstallerWindow()
        {
            Title = AppName + " " + Version + " 安装";
            Width = 1120;
            Height = 640;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            ResizeMode = ResizeMode.NoResize;
            Background = Brushes.Transparent;
            Icon = LoadImage("GPT2JSON.Icon.png");
            SnapsToDevicePixels = true;
            UseLayoutRounding = true;
            NameScope.SetNameScope(this, new NameScope());

            var root = new Canvas();
            root.Width = 1120;
            root.Height = 640;
            Content = root;

            AddBackdropRings(root);

            var outerGlow = new WpfPath
            {
                Data = OuterShellGeometry(),
                Stroke = new LinearGradientBrush(Color.FromArgb(190, 33, 210, 255), Color.FromArgb(150, 182, 75, 255), 8),
                StrokeThickness = 6,
                Fill = Brushes.Transparent,
                Opacity = 0.24,
                Effect = new BlurEffect { Radius = 7 }
            };
            Canvas.SetLeft(outerGlow, 40);
            Canvas.SetTop(outerGlow, 40);
            root.Children.Add(outerGlow);

            var main = new WpfPath
            {
                Data = ShellSurfaceGeometry(),
                Fill = new ImageBrush(LoadImage("GPT2JSON.ShellArt.png")) { Stretch = Stretch.Fill },
                Stroke = Brushes.Transparent,
                StrokeThickness = 0,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 38,
                    ShadowDepth = 0,
                    Opacity = 0.55,
                    Color = Color.FromRgb(0, 0, 0)
                }
            };
            Canvas.SetLeft(main, 40);
            Canvas.SetTop(main, 40);
            root.Children.Add(main);

            AddClosedVoidRim(root);

            var shell = new Grid
            {
                Width = 1040,
                Height = 560,
                Clip = ShellSurfaceGeometry(),
                Background = Brushes.Transparent
            };
            Canvas.SetLeft(shell, 40);
            Canvas.SetTop(shell, 40);
            root.Children.Add(shell);
            shell.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (args.ChangedButton == MouseButton.Left)
                {
                    try { DragMove(); } catch { }
                }
            };

            AddBrandLabels(shell);

            // Interior layout is arranged only after the silhouette is fixed.
            // This margin is the safe content zone that avoids the top valley,
            // bottom wave and left organic brand island.
            var content = new Grid { Margin = new Thickness(410, 70, 62, 26) };
            shell.Children.Add(content);
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(52) });
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(86) });

            var top = BuildTopBar();
            Grid.SetRow(top, 0);
            content.Children.Add(top);

            var center = BuildCenterPanel();
            Grid.SetRow(center, 1);
            content.Children.Add(center);

            var bottom = BuildBottomBar();
            Grid.SetRow(bottom, 2);
            content.Children.Add(bottom);

            _dirBox = FindName("InstallPathBox") as TextBox;
            _installButton = FindName("InstallButton") as Button;
            _progress = FindName("InstallProgress") as WpfProgressBar;
            _status = FindName("StatusText") as TextBlock;
            _closeButton = FindName("CloseButton") as Button;
            _minButton = FindName("MinButton") as Button;

            if (_dirBox != null)
                _dirBox.Text = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "GPT2JSON");
            if (_installButton != null)
                _installButton.Click += async delegate { await InstallAsync(); };
            if (_closeButton != null)
                _closeButton.Click += delegate { Close(); };
            if (_minButton != null)
                _minButton.Click += delegate { WindowState = WindowState.Minimized; };
        }

        private Geometry OuterShellGeometry()
        {
            // Visible window silhouette, in the 1040x560 local coordinate system.
            // The shape is planned first, then the panels are placed inside its safe zone:
            // - a swollen left brand island;
            // - a closed transparent "void lagoon" near the top right;
            // - a floating lower wave instead of a rectangular installer base.
            return Geometry.Parse(
                "M96,7 " +
                "C53,0 23,28 17,78 " +
                "C10,132 48,164 29,225 " +
                "C12,292 -4,338 34,397 " +
                "C72,456 34,504 82,535 " +
                "C130,568 202,548 274,550 " +
                "C370,554 446,528 514,510 " +
                "C612,485 704,517 802,544 " +
                "L970,544 " +
                "C1018,544 1040,514 1040,466 " +
                "L1040,84 " +
                "C1040,34 1008,8 958,8 " +
                "L790,8 " +
                "C712,8 662,48 560,30 " +
                "C500,19 453,18 382,44 " +
                "C328,66 280,48 224,24 " +
                "C178,8 143,15 96,7 Z");
        }

        private Geometry VoidHoleGeometry()
        {
            return Geometry.Parse(
                "M665,82 " +
                "C670,48 710,25 763,30 " +
                "C812,35 842,62 838,96 " +
                "C834,132 788,151 735,146 " +
                "C690,142 662,116 665,82 Z");
        }

        private Geometry ShellSurfaceGeometry()
        {
            return new CombinedGeometry(GeometryCombineMode.Exclude, OuterShellGeometry(), VoidHoleGeometry());
        }

        private void AddClosedVoidRim(Canvas root)
        {
            var voidGlow = new WpfPath
            {
                Data = VoidHoleGeometry(),
                StrokeThickness = 11,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                StrokeLineJoin = PenLineJoin.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(190, 31, 215, 255), Color.FromArgb(118, 187, 81, 255), 18),
                Fill = Brushes.Transparent,
                Opacity = 0.78,
                Effect = new BlurEffect { Radius = 6 }
            };
            Canvas.SetLeft(voidGlow, 40);
            Canvas.SetTop(voidGlow, 40);
            root.Children.Add(voidGlow);

            var voidEdge = new WpfPath
            {
                Data = VoidHoleGeometry(),
                StrokeThickness = 1.6,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                StrokeLineJoin = PenLineJoin.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(235, 213, 246, 255), Color.FromArgb(115, 95, 219, 255), 18),
                Fill = Brushes.Transparent,
                Opacity = 0.95
            };
            Canvas.SetLeft(voidEdge, 40);
            Canvas.SetTop(voidEdge, 40);
            root.Children.Add(voidEdge);
        }

        private void AddBackdropRings(Canvas root)
        {
            var ring1 = new WpfPath
            {
                Data = Geometry.Parse("M58,470 C185,150 520,24 780,168 C966,270 948,500 710,586 C485,668 198,596 58,470 Z"),
                StrokeThickness = 18,
                Stroke = new LinearGradientBrush(Color.FromRgb(28, 211, 255), Color.FromRgb(160, 73, 255), 30),
                Fill = Brushes.Transparent,
                Opacity = 0.62,
                Effect = new BlurEffect { Radius = 5 }
            };
            root.Children.Add(ring1);

            var ring2 = new WpfPath
            {
                Data = Geometry.Parse("M675,44 C910,86 1012,246 930,394 C842,556 560,614 310,552 C190,520 110,466 76,410"),
                StrokeThickness = 24,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(210, 43, 204, 255), Color.FromArgb(170, 180, 77, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.54,
                Effect = new BlurEffect { Radius = 8 }
            };
            root.Children.Add(ring2);

            var comet = new WpfPath
            {
                Data = Geometry.Parse("M792,42 C934,94 996,194 945,310"),
                StrokeThickness = 34,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(160, 30, 213, 255), Color.FromArgb(0, 174, 82, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.62,
                Effect = new BlurEffect { Radius = 11 }
            };
            root.Children.Add(comet);

            var lowerComet = new WpfPath
            {
                Data = Geometry.Parse("M122,580 C330,642 610,640 800,548"),
                StrokeThickness = 16,
                StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round,
                Stroke = new LinearGradientBrush(Color.FromArgb(160, 166, 70, 255), Color.FromArgb(80, 25, 209, 255), 0),
                Fill = Brushes.Transparent,
                Opacity = 0.58,
                Effect = new BlurEffect { Radius = 6 }
            };
            root.Children.Add(lowerComet);

            var aura = new Ellipse
            {
                Width = 780,
                Height = 520,
                Fill = new RadialGradientBrush(Color.FromArgb(80, 62, 151, 255), Color.FromArgb(0, 1, 7, 21)),
                Opacity = 0.55
            };
            Canvas.SetLeft(aura, 120);
            Canvas.SetTop(aura, 65);
            root.Children.Insert(0, aura);
        }

        private void AddBrandLabels(Grid shell)
        {
            var title = new TextBlock
            {
                Text = "GPT2JSON",
                Foreground = Brushes.White,
                FontSize = 38,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(95, 306, 0, 0),
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(35, 162, 255), Opacity = 0.28 }
            };
            shell.Children.Add(title);

            var sub = new TextBlock
            {
                Text = "Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(184, 205, 236)),
                FontSize = 14,
                Margin = new Thickness(103, 354, 0, 0)
            };
            shell.Children.Add(sub);

            var version = new Border
            {
                CornerRadius = new CornerRadius(12),
                Background = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(80, 255, 255, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(12, 5, 12, 5),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Bottom,
                Margin = new Thickness(114, 0, 0, 52),
                Child = new TextBlock
                {
                    Text = Version,
                    Foreground = new SolidColorBrush(Color.FromRgb(210, 225, 255)),
                    FontSize = 13,
                    FontWeight = FontWeights.SemiBold
                }
            };
            shell.Children.Add(version);
        }

        private void AddContentSafePlate(Grid shell)
        {
            var plate = new WpfPath
            {
                Data = Geometry.Parse(
                    "M430,122 " +
                    "C485,82 575,94 650,120 " +
                    "C704,139 758,120 790,92 " +
                    "C830,58 1000,72 1018,124 " +
                    "C1035,178 1022,410 1000,478 " +
                    "C980,535 900,528 790,518 " +
                    "C700,511 650,505 575,528 " +
                    "L430,528 " +
                    "C374,528 342,492 360,445 " +
                    "C385,380 376,310 358,244 " +
                    "C340,178 372,136 430,122 Z"),
                Fill = new LinearGradientBrush(Color.FromArgb(62, 255, 255, 255), Color.FromArgb(12, 255, 255, 255), 48),
                Stroke = new LinearGradientBrush(Color.FromArgb(80, 174, 224, 255), Color.FromArgb(36, 180, 92, 255), 8),
                StrokeThickness = 1.1,
                Opacity = 0.86,
                Effect = new DropShadowEffect { BlurRadius = 28, ShadowDepth = 0, Opacity = 0.22, Color = Color.FromRgb(17, 123, 201) }
            };
            shell.Children.Add(plate);
        }

        private void AddGlowGrain(Grid shell)
        {
            var dotBrush = new RadialGradientBrush(Color.FromArgb(88, 69, 224, 255), Color.FromArgb(0, 69, 224, 255));
            int[] xs = { 410, 488, 560, 642, 735, 805, 476, 682 };
            int[] ys = { 118, 88, 154, 104, 170, 96, 455, 430 };
            for (int i = 0; i < xs.Length; i++)
            {
                var e = new Ellipse { Width = 90, Height = 90, Fill = dotBrush, Opacity = 0.28 };
                e.Margin = new Thickness(xs[i], ys[i], 0, 0);
                shell.Children.Add(e);
            }
        }

        private UIElement BuildTopBar()
        {
            var grid = new Grid { Margin = new Thickness(0, 0, 0, 0) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(94) });

            var buttons = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal, HorizontalAlignment = System.Windows.HorizontalAlignment.Right };
            RegisterName("MinButton", WindowButton("—"));
            RegisterName("CloseButton", WindowButton("×"));
            buttons.Children.Add((Button)FindName("MinButton"));
            buttons.Children.Add((Button)FindName("CloseButton"));
            Grid.SetColumn(buttons, 1);
            grid.Children.Add(buttons);
            return grid;
        }

        private UIElement BuildCenterPanel()
        {
            var panel = new StackPanel { VerticalAlignment = System.Windows.VerticalAlignment.Center };

            var title = new TextBlock
            {
                Text = "GPT2JSON 安装",
                Foreground = Brushes.White,
                FontSize = 43,
                FontWeight = FontWeights.Bold,
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(43, 137, 255), Opacity = 0.18 }
            };
            panel.Children.Add(title);

            var desc = new TextBlock
            {
                Text = "轻量独立的 Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(161, 179, 214)),
                FontSize = 16,
                Margin = new Thickness(2, 8, 0, 24)
            };
            panel.Children.Add(desc);

            var features = new WrapPanel { Margin = new Thickness(0, 0, 0, 26) };
            features.Children.Add(FeaturePill("◇", "协议优先"));
            features.Children.Add(FeaturePill("▱", "批量导出"));
            features.Children.Add(FeaturePill("↯", "本地处理"));
            panel.Children.Add(features);

            var label = new TextBlock
            {
                Text = "安装位置",
                Foreground = new SolidColorBrush(Color.FromRgb(231, 240, 255)),
                FontSize = 15,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 10)
            };
            panel.Children.Add(label);

            var pathBorder = new Border
            {
                Height = 58,
                CornerRadius = new CornerRadius(18),
                Background = new SolidColorBrush(Color.FromArgb(62, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(95, 142, 195, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(18, 0, 10, 0)
            };
            var pathGrid = new Grid();
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(30) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(96) });
            var folderIcon = new TextBlock
            {
                Text = "\uE8B7",
                FontFamily = new FontFamily("Segoe MDL2 Assets"),
                Foreground = new SolidColorBrush(Color.FromRgb(179, 204, 238)),
                FontSize = 18,
                VerticalAlignment = System.Windows.VerticalAlignment.Center,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left
            };
            pathGrid.Children.Add(folderIcon);
            var box = new TextBox
            {
                Name = "InstallPathBox",
                Foreground = new SolidColorBrush(Color.FromRgb(225, 238, 255)),
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                FontSize = 15,
                VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                CaretBrush = Brushes.White
            };
            RegisterName(box.Name, box);
            Grid.SetColumn(box, 1);
            pathGrid.Children.Add(box);
            var browse = new Button
            {
                Content = "浏览",
                Height = 40,
                Margin = new Thickness(10, 8, 0, 8),
                Background = new SolidColorBrush(Color.FromArgb(55, 96, 165, 255)),
                Foreground = Brushes.White,
                BorderBrush = new SolidColorBrush(Color.FromArgb(100, 160, 205, 255)),
                Style = RoundedButtonStyle(12)
            };
            browse.Click += BrowsePath;
            Grid.SetColumn(browse, 2);
            pathGrid.Children.Add(browse);
            pathBorder.Child = pathGrid;
            panel.Children.Add(pathBorder);

            RegisterProgress(panel);
            return panel;
        }

        private UIElement BuildBottomBar()
        {
            var grid = new Grid { Margin = new Thickness(0, 0, 0, 24) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(160) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(18) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(132) });

            var install = new Button
            {
                Name = "InstallButton",
                Content = "↓  开始安装",
                Height = 54,
                FontSize = 17,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(27, 181, 255), Color.FromRgb(176, 69, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(135, 202, 232, 255)),
                Style = RoundedButtonStyle(18)
            };
            RegisterName(install.Name, install);
            Grid.SetColumn(install, 1);
            grid.Children.Add(install);

            var cancel = new Button
            {
                Content = "取消",
                Height = 54,
                FontSize = 15,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(86, 163, 190, 255)),
                Style = RoundedButtonStyle(18)
            };
            cancel.Click += delegate { Close(); };
            Grid.SetColumn(cancel, 3);
            grid.Children.Add(cancel);
            return grid;
        }

        private Border FeaturePill(string icon, string text)
        {
            var stack = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal };
            stack.Children.Add(new TextBlock
            {
                Text = icon,
                Foreground = new SolidColorBrush(Color.FromRgb(96, 186, 255)),
                FontSize = 15,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 8, 0),
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            stack.Children.Add(new TextBlock
            {
                Text = text,
                Foreground = new SolidColorBrush(Color.FromRgb(220, 233, 255)),
                FontSize = 13,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            return new Border
            {
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(13, 7, 13, 7),
                Margin = new Thickness(0, 0, 10, 8),
                Background = new LinearGradientBrush(Color.FromArgb(42, 255, 255, 255), Color.FromArgb(24, 107, 155, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(70, 130, 204, 255)),
                BorderThickness = new Thickness(1),
                Child = stack
            };
        }

        private bool RegisterProgress(StackPanel panel)
        {
            var progress = new WpfProgressBar
            {
                Name = "InstallProgress",
                Height = 5,
                Minimum = 0,
                Maximum = 100,
                Value = 0,
                Margin = new Thickness(0, 22, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(54, 210, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderThickness = new Thickness(0)
            };
            RegisterName(progress.Name, progress);
            panel.Children.Add(progress);

            var status = new TextBlock
            {
                Name = "StatusText",
                Text = "准备就绪：选择目录后即可开始安装。",
                Foreground = new SolidColorBrush(Color.FromRgb(137, 158, 196)),
                FontSize = 12,
                Margin = new Thickness(2, 10, 0, 0)
            };
            RegisterName(status.Name, status);
            panel.Children.Add(status);
            return true;
        }

        private Button WindowButton(string text)
        {
            return new Button
            {
                Content = text,
                Width = 42,
                Height = 34,
                Margin = new Thickness(5, 0, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(217, 229, 255)),
                Background = new SolidColorBrush(Color.FromArgb(32, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                FontSize = text == "×" ? 20 : 15,
                Style = RoundedButtonStyle(17)
            };
        }

        private Style RoundedButtonStyle(double radius)
        {
            var style = new Style(typeof(Button));
            var border = new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(radius));
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(Button.BackgroundProperty));
            border.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(Button.BorderBrushProperty));
            border.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(Button.BorderThicknessProperty));
            var content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, System.Windows.HorizontalAlignment.Center);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, System.Windows.VerticalAlignment.Center);
            border.AppendChild(content);
            var template = new ControlTemplate(typeof(Button));
            template.VisualTree = border;
            style.Setters.Add(new Setter(Button.TemplateProperty, template));
            style.Setters.Add(new Setter(Button.CursorProperty, System.Windows.Input.Cursors.Hand));
            style.Setters.Add(new Setter(Button.PaddingProperty, new Thickness(10, 0, 10, 0)));
            return style;
        }

        private void BrowsePath(object sender, RoutedEventArgs e)
        {
            using (var dlg = new FolderBrowserDialog())
            {
                dlg.Description = "选择 GPT2JSON 安装目录";
                dlg.SelectedPath = _dirBox != null ? _dirBox.Text : string.Empty;
                if (dlg.ShowDialog() == System.Windows.Forms.DialogResult.OK && _dirBox != null)
                    _dirBox.Text = dlg.SelectedPath;
            }
        }

        private async Task InstallAsync()
        {
            if (_dirBox == null || string.IsNullOrWhiteSpace(_dirBox.Text))
            {
                MessageBox.Show("请先选择安装目录。", AppName, MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            SetBusy(true, "正在释放安装核心…", 18);
            try
            {
                string installerPath = ExtractInstaller();
                Directory.CreateDirectory(_dirBox.Text);
                SetBusy(true, "安装核心已就绪，正在写入文件…", 42);
                int code = await Task.Run(delegate
                {
                    var psi = new ProcessStartInfo
                    {
                        FileName = installerPath,
                        Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=\"" + _dirBox.Text + "\"",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    var p = Process.Start(psi);
                    p.WaitForExit();
                    return p.ExitCode;
                });

                if (code != 0)
                    throw new InvalidOperationException("安装核心返回错误码：" + code);

                SetBusy(false, "安装完成：GPT2JSON 已准备好。", 100);
                TryLaunchInstalledApp();
            }
            catch (Exception ex)
            {
                SetBusy(false, "安装失败：" + ex.Message, 0);
                MessageBox.Show(ex.Message, AppName + " 安装失败", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void SetBusy(bool busy, string text, double progress)
        {
            if (_installButton != null) _installButton.IsEnabled = !busy;
            if (_dirBox != null) _dirBox.IsEnabled = !busy;
            if (_status != null) _status.Text = text;
            if (_progress != null) _progress.Value = progress;
        }

        private string ExtractInstaller()
        {
            string dir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "GPT2JSON-ArtSetup", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string path = System.IO.Path.Combine(dir, "GPT2JSON-Setup-v0.1.0.exe");
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("GPT2JSON.Setup.exe"))
            {
                if (input == null) throw new FileNotFoundException("未找到内嵌安装核心。", "GPT2JSON.Setup.exe");
                using (var output = File.Create(path))
                {
                    input.CopyTo(output);
                }
            }
            return path;
        }

        private void TryLaunchInstalledApp()
        {
            try
            {
                string exe = System.IO.Path.Combine(_dirBox.Text, "GPT2JSON.exe");
                if (File.Exists(exe))
                    Process.Start(new ProcessStartInfo { FileName = exe, UseShellExecute = true });
            }
            catch { }
        }

        private BitmapImage LoadImage(string resourceName)
        {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (stream == null) return null;
                var memory = new MemoryStream();
                stream.CopyTo(memory);
                memory.Position = 0;
                var image = new BitmapImage();
                image.BeginInit();
                image.CacheOption = BitmapCacheOption.OnLoad;
                image.StreamSource = memory;
                image.EndInit();
                image.Freeze();
                return image;
            }
        }
    }
}






