import itertools
from collections import OrderedDict
from itertools import compress

import bokeh
import interpret
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sklearn
from bokeh.models import BoxSelectTool
from bokeh.plotting import figure, output_file

from pyautoml.modelling.model_explanation import (INTERPRET_EXPLAINERS,
                                                  MSFTInterpret, Shap)
from pyautoml.visualizations.visualize import *

SCORE_METRICS = [
    'accuracy',
    'average_precision',
    'balanced_accuracy',
    'cohen_kappa',
    'f1',
    'jaccard',
    'precision',
    'recall',
    'roc_auc',
]

SHAP_LEARNERS = {
    sklearn.linear_model.LogisticRegression : 'linear'
}

PROBLEM_TYPE = {
    sklearn.linear_model.LogisticRegression : 'classification'
}

class ModelBase(object):

    # TODO: Add more SHAP use cases
    # TODO: Add loss metrics

    def __init__(self, model_object, model, model_name):
        
        self.model = model
        self.model_name = model_name
        self.data = model_object._data_properties.data
        self.x_train = model_object._data_properties.x_train
        self.x_test = model_object._data_properties.x_test
        self.data_results = model_object._result_data
        self.x_train_results = model_object._train_result_data
        self.x_test_results = model_object._test_result_data
        self.report = model_object._data_properties.report

        if isinstance(self, ClassificationModel) or isinstance(self, RegressionModel):
            self.shap = Shap(self.model, self.x_train, self.x_test, self.target_data, SHAP_LEARNERS[type(self.model)])
            self.interpret = MSFTInterpret(self.model, self.x_train, self.x_test, self.target_data, PROBLEM_TYPE[type(self.model)])
        else:
            self.shap = None
            self.interpret = None

    def model_weights(self):
        """
        Prints and logs all the features ranked by importance from most to least important.
        
        Returns
        -------
        dict
            Dictionary of features and their corresponding weights
        
        Raises
        ------
        AttributeError
            If model does not have coefficients to display
        """

        report_strings = []

        try:
            model_dict = dict(zip(self.features, self.model.coef_.flatten()))
        except Exception as e:
            raise AttributeError('Model does not have coefficients to view.')

        sorted_features = OrderedDict(sorted(model_dict.items(), key=lambda kv: abs(kv[1]), reverse=True))

        for feature, weight in sorted_features.items():
            report_string = '\t{} : {:.2f}'.format(feature, weight)
            report_strings.append(report_string)

            print(report_string.strip())

        if self.report:
            self.report.log('Features ranked from most to least important:\n')
            self.report.write_contents("\n".join(report_strings))

        return sorted_features

    def summary_plot(self, **summaryplot_kwargs):
        """
        Create a SHAP summary plot, colored by feature values when they are provided.

        For a list of all kwargs please see the Shap documentation : https://shap.readthedocs.io/en/latest/#plots

        Parameters
        ----------
        max_display : int
            How many top features to include in the plot (default is 20, or 7 for interaction plots), by default None
            
        plot_type : "dot" (default for single output), "bar" (default for multi-output), "violin", or "compact_dot"
            What type of summary plot to produce. Note that "compact_dot" is only used for SHAP interaction values.

        color : str or matplotlib.colors.ColorMap 
            Color spectrum used to draw the plot lines. If str, a registered matplotlib color name is assumed.

        axis_color : str or int 
            Color used to draw plot axes.

        title : str 
            Title of the plot.

        alpha : float 
            Alpha blending value in [0, 1] used to draw plot lines.

        show : bool 
            Whether to automatically display the plot.

        sort : bool
            Whether to sort features by importance, by default True

        color_bar : bool 
            Whether to draw the color bar.

        auto_size_plot : bool 
            Whether to automatically size the matplotlib plot to fit the number of features displayed. If False, specify the plot size using matplotlib before calling this function.

        layered_violin_max_num_bins : int
            Max number of bins, by default 20

        **summaryplot_kwargs
            For more info see https://shap.readthedocs.io/en/latest/#plots
        
        Raises
        ------
        NotImplementedError
            Currently implemented for Linear and Tree models.
        """

        if self.shap is None:
            raise NotImplementedError('SHAP is not implemented yet for {}'.format(type(self)))

        self.shap.summary_plot(**summaryplot_kwargs)

    def decision_plot(self, num_samples=0.6, sample_no=None, highlight_misclassified=False, **decisionplot_kwargs):
        """
        Visualize model decisions using cumulative SHAP values.
        
        Each colored line in the plot represents the model prediction for a single observation. 
        
        Note that plotting too many samples at once can make the plot unintelligible.

        When is a decision plot useful:        
            - Show a large number of feature effects clearly.
            
            - Visualize multioutput predictions.
            
            - Display the cumulative effect of interactions.
            
            - Explore feature effects for a range of feature values.
            
            - Identify outliers.
            
            - Identify typical prediction paths.
            
            - Compare and contrast predictions for several models.

        Explanation:
            - The plot is centered on the x-axis at the models expected value.

            - All SHAP values are relative to the model's expected value like a linear model's effects are relative to the intercept.
            
            - The y-axis lists the model's features. By default, the features are ordered by descending importance. 
            
            - The importance is calculated over the observations plotted. This is usually different than the importance ordering for the entire dataset. In addition to feature importance ordering, the decision plot also supports hierarchical cluster feature ordering and user-defined feature ordering.
            
            - Each observation's prediction is represented by a colored line. 
            
            - At the top of the plot, each line strikes the x-axis at its corresponding observation's predicted value. This value determines the color of the line on a spectrum.
            
            - Moving from the bottom of the plot to the top, SHAP values for each feature are added to the model's base value. This shows how each feature contributes to the overall prediction.
            
            - At the bottom of the plot, the observations converge at the models expected value.

        Parameters
        ----------
        num_samples : int, float, or 'all', optional
            Number of samples to display, if less than 1 it will treat it as a percentage, 'all' will include all samples
            , by default 0.6

        sample_no : int, optional
            Sample number to isolate and analyze, if provided it overrides num_samples, by default None

        highlight_misclassified : bool, optional
            True to highlight the misclassified results, by default False

        feature_order : str or None or list or numpy.ndarray
            Any of "importance" (the default), "hclust" (hierarchical clustering), "none", or a list/array of indices.
            hclust is useful for finding outliers.

        feature_display_range: slice or range
            The slice or range of features to plot after ordering features by feature_order. A step of 1 or None will display the features in ascending order. A step of -1 will display the features in descending order. If feature_display_range=None, slice(-1, -21, -1) is used (i.e. show the last 20 features in descending order). If shap_values contains interaction values, the number of features is automatically expanded to include all possible interactions: N(N + 1)/2 where N = shap_values.shape[1].

        highlight : Any 
            Specify which observations to draw in a different line style. All numpy indexing methods are supported. For example, list of integer indices, or a bool array.

        link : str 
            Use "identity" or "logit" to specify the transformation used for the x-axis. The "logit" link transforms log-odds into probabilities.

        plot_color : str or matplotlib.colors.ColorMap 
            Color spectrum used to draw the plot lines. If str, a registered matplotlib color name is assumed.

        axis_color : str or int 
            Color used to draw plot axes.

        y_demarc_color : str or int 
            Color used to draw feature demarcation lines on the y-axis.

        alpha : float 
            Alpha blending value in [0, 1] used to draw plot lines.

        color_bar : bool 
            Whether to draw the color bar.

        auto_size_plot : bool 
            Whether to automatically size the matplotlib plot to fit the number of features displayed. If False, specify the plot size using matplotlib before calling this function.

        title : str 
            Title of the plot.

        xlim: tuple[float, float] 
            The extents of the x-axis (e.g. (-1.0, 1.0)). If not specified, the limits are determined by the maximum/minimum predictions centered around base_value when link='identity'. When link='logit', the x-axis extents are (0, 1) centered at 0.5. x_lim values are not transformed by the link function. This argument is provided to simplify producing multiple plots on the same scale for comparison.

        show : bool 
            Whether to automatically display the plot.

        return_objects : bool 
            Whether to return a DecisionPlotResult object containing various plotting features. This can be used to generate multiple decision plots using the same feature ordering and scale, by default True.

        ignore_warnings : bool 
            Plotting many data points or too many features at a time may be slow, or may create very large plots. Set this argument to True to override hard-coded limits that prevent plotting large amounts of data.

        new_base_value : float 
            SHAP values are relative to a base value; by default, the expected value of the model's raw predictions. Use new_base_value to shift the base value to an arbitrary value (e.g. the cutoff point for a binary classification task).

        legend_labels : list of str 
            List of legend labels. If None, legend will not be shown.

        legend_location : str 
            Legend location. Any of "best", "upper right", "upper left", "lower left", "lower right", "right", "center left", "center right", "lower center", "upper center", "center".
    
        Raises
        ------
        NotImplementedError
            Currently implemented for Linear and Tree models.

        Returns
        -------
        DecisionPlotResult 
            If return_objects=True (the default). Returns None otherwise.

        Example
        --------
        Plot two decision plots using the same feature order and x-axis.

        >>> r = model.model_name.decision_plot()
        >>> model.model_name.decision_plot(no_sample=42, feature_order=r.feature_idx, xlim=r.xlim)
        """   

        if self.shap is None:
            raise NotImplementedError('SHAP is not implemented yet for {}'.format(type(self)))

        if highlight_misclassified:
            if not any(self.shap.misclassified_values):
                raise AttributeError('There are no misclassified values!')
            
            decisionplot_kwargs['highlight'] = self.shap.misclassified_values

        return self.shap.decision_plot(num_samples, sample_no, **decisionplot_kwargs)

    def force_plot(self, sample_no=None, misclassified=False, **forceplot_kwargs):
        """
        Visualize the given SHAP values with an additive force layout
        
        Parameters
        ----------
        sample_no : int, optional
            Sample number to isolate and analyze, by default None

        misclassified : bool, optional
            True to only show the misclassified results, by default False

        link : "identity" or "logit"
            The transformation used when drawing the tick mark labels. Using logit will change log-odds numbers
            into probabilities. 

        matplotlib : bool
            Whether to use the default Javascript output, or the (less developed) matplotlib output. Using matplotlib
            can be helpful in scenarios where rendering Javascript/HTML is inconvenient. 
        
        Raises
        ------
        NotImplementedError
            Currently implemented for Linear and Tree models.

        Example
        --------
        Plot two decision plots using the same feature order and x-axis.

        >>> model.model_name.force_plot() # The entire test dataset
        >>> model.model_name.forceplot(no_sample=1, misclassified=True) # Analyze the first misclassified result
        """

        if self.shap is None:
            raise NotImplementedError('SHAP is not implemented yet for {}'.format(type(self)))

        if misclassified:
            if not any(self.shap.misclassified_values):
                raise AttributeError('There are no misclassified values!')
            
            forceplot_kwargs['shap_values'] = self.shap.shap_values[self.shap.misclassified_values]

        return self.shap.force_plot(sample_no, **forceplot_kwargs)

    def dependence_plot(self, feature: str, interaction='auto', **dependenceplot_kwargs):
        """
        A dependence plot is a scatter plot that shows the effect a single feature has on the predictions made by the mode.

        Explanation:
            - Each dot is a single prediction (row) from the dataset.
        
            - The x-axis is the value of the feature (from the X matrix).

            - The y-axis is the SHAP value for that feature, which represents how much knowing that feature's value changes the output of the model for that sample's prediction.

            - The color corresponds to a second feature that may have an interaction effect with the feature we are plotting (by default this second feature is chosen automatically). 
            
            - If an interaction effect is present between this other feature and the feature we are plotting it will show up as a distinct vertical pattern of coloring. 
        
        Parameters
        ----------
        feature : str
            Feature who's impact on the model you want to analyze

        interaction : "auto", None, int, or string
            The index of the feature used to color the plot. The name of a feature can also be passed as a string. If "auto" then shap.common.approximate_interactions is used to pick what seems to be the strongest interaction (note that to find to true stongest interaction you need to compute the SHAP interaction values).

        x_jitter : float (0 - 1)
            Adds random jitter to feature values. May increase plot readability when feature is discrete.

        alpha : float
            The transparency of the data points (between 0 and 1). This can be useful to the show density of the data points when using a large dataset.

        xmin : float or string
            Represents the lower bound of the plot's x-axis. It can be a string of the format "percentile(float)" to denote that percentile of the feature's value used on the x-axis.

        xmax : float or string
            Represents the upper bound of the plot's x-axis. It can be a string of the format "percentile(float)" to denote that percentile of the feature's value used on the x-axis.

        ax : matplotlib Axes object
            Optionally specify an existing matplotlib Axes object, into which the plot will be placed. In this case we do not create a Figure, otherwise we do.

        cmap : str or matplotlib.colors.ColorMap 
            Color spectrum used to draw the plot lines. If str, a registered matplotlib color name is assumed.

        Raises
        ------
        NotImplementedError
            Currently implemented for Linear and Tree models.
        """

        if self.shap is None:
            raise NotImplementedError('SHAP is not implemented yet for {}'.format(type(self)))

        self.shap.dependence_plot(feature, interaction, **dependenceplot_kwargs)

    def shap_get_misclassified_index(self):
        """
        Prints the sample numbers of misclassified samples.
        """

        sample_list = list(compress(range(len(self.shap.misclassified_values)), self.shap.misclassified_values))

        print(", ".join(str(np.array(sample_list) + 1)))

    def interpret_model(self, show=True):
        """
        Displays a dashboard interpreting your model's performance, behaviour and individual predictions.

        If you have run any other `interpret` functions, they will be included in the dashboard, otherwise all the other intrepretable methods will be included in the dashboard.
        """

        if show:
            self.interpret.create_dashboard()

    def interpret_model_performance(self, method='all', predictions='default', show=True, **interpret_kwargs):
        """
        Plots an interpretable display of your model based off a performance metric.

        Can either be 'ROC' or 'PR' for precision, recall for classification problems.

        Can be 'regperf' for regression problems.

        If 'all' a dashboard is displayed with the corresponding explainers for the problem type.

        ROC: Receiver Operator Characteristic
        PR: Precision Recall
        regperf: RegeressionPerf
        
        Parameters
        ----------
        method : str
            Performance metric, either 'all', 'roc' or 'PR', by default 'all'

        predictions : str, optional
            Prediction type, can either be 'default' (.predict) or 'probability' if the model can predict probabilities, by default 'default'

        show : bool, optional 
            False to not display the plot, by default True
        """
        
        dashboard = []

        if method == 'all':
            for explainer in INTERPRET_EXPLAINERS['problem'][self.interpret.problem]:
                dashboard.append(self.interpret.blackbox_show_performance(method=explainer, predictions=predictions, show=False, **interpret_kwargs))

            if show:
                interpret.show(dashboard)
        else:
            self.interpret.blackbox_show_performance(method=method, predictions=predictions, show=show, **interpret_kwargs)

    def interpret_predictions(self, num_samples=0.25, sample_no=None, method='all', predictions='default', show=True, **interpret_kwargs):
        """
        Plots an interpretable display that explains individual predictions of your model.

        Supported explainers are either 'lime' or 'shap'.

        If 'all' a dashboard is displayed with morris and dependence analysis displayed.
        
        Parameters
        ----------
        num_samples : int, float, or 'all', optional
            Number of samples to display, if less than 1 it will treat it as a percentage, 'all' will include all samples
            , by default 0.25

        sample_no : int, optional
            Sample number to isolate and analyze, if provided it overrides num_samples, by default None

        method : str, optional
            Explainer type, can either be 'all', 'lime', or 'shap', by default 'all'

        predictions : str, optional
            Prediction type, can either be 'default' (.predict) or 'probability' if the model can predict probabilities, by default 'default'

        show : bool, optional 
            False to not display the plot, by default True
        """

        dashboard = []

        if method == 'all':
            for explainer in INTERPRET_EXPLAINERS['local']:
                dashboard.append(self.interpret.blackbox_local_explanation(num_samples=num_samples, sample_no=sample_no, method=explainer, predictions=predictions, show=False, **interpret_kwargs))

            if show:
                interpret.show(dashboard)
        else:
            self.interpret.blackbox_local_explanation(num_samples=num_samples, sample_no=sample_no, method=method, predictions=predictions, show=show, **interpret_kwargs)
        
    def interpret_model_behavior(self, method='all', predictions='default', show=True, **interpret_kwargs):
        """
        Provides an interpretable summary of your models behaviour based off an explainer.

        Can either be 'morris' or 'dependence' for Partial Dependence.
        
        If 'all' a dashboard is displayed with morris and dependence analysis displayed.
        
        Parameters
        ----------
        method : str, optional
            Explainer type, can either be 'all', 'morris' or 'dependence', by default 'all'

        predictions : str, optional
            Prediction type, can either be 'default' (.predict) or 'probability' if the model can predict probabilities, by default 'default'

        show : bool, optional 
            False to not display the plot, by default True
        """

        dashboard = []

        if method == 'all':
            for explainer in INTERPRET_EXPLAINERS['global']:
                dashboard.append(self.interpret.blackbox_global_explanation(method=explainer, predictions=predictions, show=False, **interpret_kwargs))

            if show:
                interpret.show(dashboard)
        else:
            self.interpret.blackbox_global_explanation(method=method, predictions=predictions, show=show, **interpret_kwargs)
        
class TextModel(ModelBase):

    def __init__(self, model_object, model_name):
        
        model = None

        super().__init__(model_object, model, model_name)

class ClusterModel(ModelBase):

    # TODO: Add scatterplot of clusters

    def __init__(self, model_object, model_name, model, cluster_col):

        super().__init__(model_object, model, model_name)

        self.cluster_col = cluster_col

        if self.data is not None:
            self.prediction_data = self.data_results[cluster_col]
        else:
            self.train_prediction_data = self.x_train_results[cluster_col]
            self.test_prediction_data = self.x_test_results[cluster_col]

    def filter_cluster(self, cluster_no: int):
        """
        Filters data by a cluster number for analysis.
        
        Parameters
        ----------
        cluster_no : int
            Cluster number to filter by
        
        Returns
        -------
        Dataframe
            Filtered data or test dataframe
        """

        if self.data is not None:
            return self.data_results[self.data_results[self.cluster_col] == cluster_no]
        else:
            return self.x_test_results[self.x_test_results[self.cluster_col] == cluster_no]

class ClassificationModel(ModelBase):

    def __init__(self, model_object, model_name, model, predictions_col):
        
        self.target_data = model_object.target_data if model_object.target_data else model_object.y_test

        super().__init__(model_object, model, model_name)

        self.target_mapping = model_object.target_mapping

        if self.data is not None:            
            self.prediction_data = self.data_results[predictions_col]
        else:
            self.prediction_data = self.x_test_results[predictions_col]

        if self.report:
            self.report.write_header('Analyzing Model {}: '.format(self.model_name.upper()))

        if self.target_mapping is None:
            self.classes = [str(item) for item in np.unique(list(self.target_data) + list(self.prediction_data))]
        else:
            self.classes = [str(item) for item in self.target_mapping.values()]

        self.features = self.x_test.columns

    def metric(self, *metrics, metric='accuracy', **scoring_kwargs):
        """
        Measures how well your model performed based off a certain metric. It can be any combination of the ones below or 'all' for 
        every metric listed below. The default measure is accuracy.

        For more detailed information and parameters please see the following link: https://scikit-learn.org/stable/modules/classes.html#classification-metrics

        Supported metrics are:

            all : Everything below.
            accuracy : Accuracy classification score.
            average_precision : Compute average precision (AP) from prediction scores
            balanced_accuracy : Compute the balanced accuracy
            cohen_kappa : Cohen’s kappa: a statistic that measures inter-annotator agreement.
            f1 : Compute the F1 score, also known as balanced F-score or F-measure
            fbeta : Compute the F-beta score
            jaccard : Jaccard similarity coefficient score
            precision : Compute the precision
            recall : Compute the recall
            roc_auc : Compute Area Under the Receiver Operating Characteristic Curve (ROC AUC) from prediction scores.
        
        Parameters
        ----------
        metric : str, optional
            Specific type of metric, by default 'accuracy'
        """

        y_true = self.target_data
        y_pred = self.prediction_data
        computed_metrics = []


        if metric == 'all' or 'all' in metrics:
            for met in SCORE_METRICS:
                metric_str = '{} : {}'.format(met, getattr(sklearn.metrics, met + "_score")(y_true, y_pred))
                computed_metrics.append(metric_str)
                print(metric_str)
        elif metrics:
            for met in metrics:
                metric_str = '{} : {}'.format(met, getattr(sklearn.metrics, met + "_score")(y_true, y_pred))
                computed_metrics.append(metric_str)
                print(metric_str)
        else:      
            metric_str = '{} : {}'.format(met, getattr(sklearn.metrics, met + "_score")(y_true, y_pred, **scoring_kwargs))
            computed_metrics.append(metric_str)
            print(metric_str)

        if self.report:
            self.report.log('Metrics:\n')
            self.report.log('\n'.join(computed_metrics))

    def confusion_matrix(self, title=None, normalize=False, hide_counts=False, x_tick_rotation=0, figsize=None, cmap='Blues', title_fontsize="large", text_fontsize="medium"):
        """
        Prints a confusion matrix as a heatmap.
    
        Arguments
        ---------
        title : str
            The text to display at the top of the matrix, by default 'Confusion Matrix'

        normalize : bool
            If False, plot the raw numbers
            If True, plot the proportions,
            by default False

        hide_counts : bool
            If False, display the counts and percentage
            If True, hide display of the counts and percentage
            by default, False

        x_tick_rotation : int
            Degree of rotation to rotate the x ticks
            by default, 0

        figsize : tuple(int, int)
            Size of the figure
            by default, None

        cmap : str   
            The gradient of the values displayed from matplotlib.pyplot.cm
            see http://matplotlib.org/examples/color/colormaps_reference.html
            plt.get_cmap('jet') or plt.cm.Blues
            by default, 'Blues'

        title_fontsize : str
            Size of the title, by default 'large'

        text_fontsize : str
            Size of the text of the rest of the plot, by default 'medium'        
        """
        
        y_true = self.target_data
        y_pred = self.prediction_data

        if figsize:
            plt.figure(figsize=figsize)

        confusion_matrix = sklearn.metrics.confusion_matrix(y_true, y_pred)

        if normalize:
            confusion_matrix = confusion_matrix.astype('float') / confusion_matrix.sum(axis=1)[:, np.newaxis]

        accuracy = np.trace(confusion_matrix) / float(np.sum(confusion_matrix))
        mis_class = 1 - accuracy

        if title:
            plt.title(title, fontsize=title_fontsize)
        elif normalize:
            plt.title('Normalized Confusion Matrix', fontsize=title_fontsize)
        else:
            plt.title('Confusion Matrix', fontsize=title_fontsize)

        cm_sum = np.sum(confusion_matrix, axis=1)
        cm_perc = confusion_matrix / cm_sum.astype(float) * 100
        nrows, ncols = confusion_matrix.shape

        if not hide_counts:
            annot = np.zeros_like(confusion_matrix).astype('str')

            for i in range(nrows):
                for j in range(ncols):
                    c = confusion_matrix[i, j]
                    p = cm_perc[i, j]
                    if i == j:
                        s = cm_sum[i]
                        annot[i, j] = '{:.2f}%\n{}/{}'.format(float(p), int(c), int(s))
                    elif c == 0:
                        annot[i, j] = ''
                    else:
                        annot[i, j] = '{:.2f}%\n{}'.format(p, c)
        else:
            annot = np.zeros_like(confusion_matrix, dtype=str)

        df_cm = pd.DataFrame(
            confusion_matrix, index=self.classes, columns=self.classes, 
        )

        heatmap = sns.heatmap(df_cm, annot=annot, square=True, cmap=plt.cm.get_cmap(cmap), fmt='')       

        plt.tight_layout()
        plt.ylabel('True label', fontsize=text_fontsize)
        plt.xlabel('Predicted label\naccuracy={:0.4f}; misclassified={:0.4f}'.format(accuracy, mis_class), fontsize=text_fontsize)
        plt.xticks(np.arange(len(self.classes)) + 0.5, self.classes, rotation=x_tick_rotation)
        plt.show()

        if self.report:
            self.report.log('CONFUSION MATRIX:\n')
            self.report.log(df_cm.to_string())

    def roc_curve(self, figsize=(450,550), output_file=''):
        """
        Plots an ROC curve and displays the ROC statistics (area under the curve).

        Parameters
        ----------
        figsize : tuple(int, int), optional
            Figure size, by default (450,550)

        output_file : str, optional
            If a name is provided save the plot to an html file, by default ''
        """

        if len(np.unique(list(self.target_data) + list(self.prediction_data))) > 2:
            raise NotImplementedError('ROC Curve is currently not implemented for multiclassification problems.')

        y_true = self.target_data
        y_pred = self.prediction_data

        fpr, tpr, thresholds = sklearn.metrics.roc_curve(y_true, y_pred)
        roc_auc = sklearn.metrics.roc_auc_score(y_true, y_pred)

        step = 1 / (len(fpr) - 1)
        random = np.arange(0, 1 + step, step)

        p = figure(plot_width=figsize[0], plot_height=figsize[1], title='ROC Curve (Area = {:.2f})'.format(roc_auc), x_range=[0,1], y_range=[0,1], x_axis_label='False Positive Rate or (1 - Specifity)', y_axis_label='True Positive Rate or (Sensitivity)', tooltips=[('False Positive Rate', '$x'), ('True Positve Rate', '$y')], tools='pan,wheel_zoom,tap,box_zoom,reset', active_drag='box_zoom', active_scroll='wheel_zoom')

        p.line(fpr, tpr, color='blue', alpha=0.8, legend='ROC')
        p.line(random, random, color='orange', line_dash='dashed', legend='Baseline')

        p.legend.location = "bottom_right"
        p.legend.click_policy = "hide"

        if output_file:
            output_file(output_file + '.html', title='ROC Curve (area = {:.2f})'.format(roc_auc))


        bokeh.io.show(p)
    
    def classification_report(self):
        """
        Prints and logs the classification report.

        The classification report displays and logs the information in this format:

                    precision    recall  f1-score   support

                    1       1.00      0.67      0.80         3
                    2       0.00      0.00      0.00         0
                    3       0.00      0.00      0.00         0

            micro avg       1.00      0.67      0.80         3
            macro avg       0.33      0.22      0.27         3
         weighted avg       1.00      0.67      0.80         3
        """

        classification_report = sklearn.metrics.classification_report(self.target_data, self.target_data, target_names=self.classes, digits=2)

        if self.report:
            self.report.report_classification_report(classification_report)

        print(classification_report)        

class RegressionModel(ModelBase):
    # TODO: Summary statistics
    # TODO: Errors

    pass
